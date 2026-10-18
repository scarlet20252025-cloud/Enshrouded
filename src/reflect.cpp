// ============================================================================
//  WolfMount — runtime reflection-table reader (implementation)
//
//  See reflect.h for the record layout and the "validate, never trust"
//  strategy. The short version: we find a type by scanning `.rdata` for the
//  FNV-1a-32 of its qualified name, then accept the candidate record only when
//  it corroborates itself twice over:
//
//      * record[+0x50] == the hash we searched for, and
//      * record[+0x20] points at a readable string whose own FNV-1a-32 hash
//        equals that same value.
//
//  A wrong candidate therefore cannot survive: the name string has to hash to
//  the value that led us to it.
// ============================================================================

#include "reflect.h"

#include "logging.h"

#include <windows.h>

#include <cstring>
#include <mutex>
#include <unordered_map>

namespace wolfmount::reflect {

namespace {

// --- PE section lookup ------------------------------------------------------

struct Section {
    const uint8_t* base = nullptr;   // runtime VA of the section start
    size_t         size = 0;
};

// Cached .rdata range of the game module.
Section g_rdata;
bool    g_rdataResolved = false;

HMODULE GameModule() {
    static HMODULE mod = nullptr;
    if (!mod) {
        mod = GetModuleHandleA("enshrouded.exe");
        if (!mod) mod = GetModuleHandleA("enshrouded_server.exe");
    }
    return mod;
}

// Locate the section that contains `rva` and return its runtime extent.
bool FindSection(const char* wantName, Section* out) {
    HMODULE mod = GameModule();
    if (!mod) return false;

    const auto* base = reinterpret_cast<const uint8_t*>(mod);
    const auto* dos  = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return false;

    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return false;

    const IMAGE_SECTION_HEADER* sec = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i) {
        char name[9] = {0};
        memcpy(name, sec[i].Name, 8);
        if (wantName && strcmp(name, wantName) != 0) continue;
        out->base = base + sec[i].VirtualAddress;
        out->size = sec[i].Misc.VirtualSize;
        return true;
    }
    return false;
}

bool Rdata(Section* out) {
    if (!g_rdataResolved) {
        g_rdataResolved = true;   // resolve once, even on failure
        if (!FindSection(".rdata", &g_rdata)) {
            g_rdata = Section{};
            WM_MOD_LOG("[wolfmount/reflect] .rdata not found");
        }
    }
    *out = g_rdata;
    return g_rdata.base != nullptr && g_rdata.size != 0;
}

// --- safe reads -------------------------------------------------------------

bool Readable(const void* p, size_t n) {
    if (!p || n == 0) return false;
    // IsBadReadPtr is deprecated but is exactly the primitive we want here:
    // a cheap "would this dereference fault?" probe with no allocation.
    return !IsBadReadPtr(p, static_cast<UINT_PTR>(n));
}

const char* ReadCString(const void* p, size_t maxLen) {
    if (!Readable(p, 1)) return nullptr;
    const char* s = static_cast<const char*>(p);
    // Probe the whole window first so a truncated/missing NUL cannot fault.
    if (!Readable(s, maxLen)) {
        // Fall back to a page-at-a-time probe below.
        for (size_t i = 0; i < maxLen; ++i) {
            if (!Readable(s + i, 1)) return nullptr;
            if (s[i] == '\0') return s;
        }
        return nullptr;
    }
    for (size_t i = 0; i < maxLen; ++i) {
        if (s[i] == '\0') return s;
    }
    return nullptr;
}

bool LooksLikeQualifiedName(const char* s, size_t maxLen) {
    if (!s || !Readable(s, 1)) return false;
    const size_t len = strnlen(s, maxLen);
    if (len < 4 || len >= maxLen) return false;
    if (!Readable(s, len + 1)) return false;
    // Must be printable ASCII, and must look like a scoped C++ name.
    bool sawScope = false;
    for (size_t i = 0; i < len; ++i) {
        const unsigned char c = static_cast<unsigned char>(s[i]);
        if (c < 0x20 || c > 0x7E) return false;
        if (c == ':') sawScope = true;
    }
    return sawScope;
}

// --- the record -------------------------------------------------------------

// Offsets inside a 0x90-byte TypeMetadata record (see reflect.h).
constexpr size_t kOffName          = 0x00;
constexpr size_t kOffQualifiedName = 0x20;
constexpr size_t kOffSize          = 0x40;
constexpr size_t kOffFieldCount    = 0x48;
constexpr size_t kOffPrimitiveType = 0x4C;
constexpr size_t kOffQualifiedHash = 0x50;
constexpr size_t kOffInternalHash  = 0x54;
constexpr size_t kOffStructFields  = 0x58;
constexpr size_t kRecordSize       = 0x90;

// A struct field entry is 24 bytes.
constexpr size_t kFieldEntrySize   = 24;
constexpr size_t kFieldOffName     = 0x00;
constexpr size_t kFieldOffType     = 0x10;
constexpr size_t kFieldOffDataOff  = 0x18;

uint32_t ReadU32(const void* p, size_t off) {
    uint32_t v = 0;
    memcpy(&v, static_cast<const uint8_t*>(p) + off, 4);
    return v;
}

uint64_t ReadU64(const void* p, size_t off) {
    uint64_t v = 0;
    memcpy(&v, static_cast<const uint8_t*>(p) + off, 8);
    return v;
}

// Fill a TypeInfo from what is believed to be a record. Returns false when the
// bytes there fail the self-consistency checks.
bool LoadRecord(const void* record, uint32_t expectHash, TypeInfo* out) {
    if (!Readable(record, kRecordSize)) return false;
    if (ReadU32(record, kOffQualifiedHash) != expectHash) return false;

    const char* qname = ReadCString(
        reinterpret_cast<const void*>(ReadU64(record, kOffQualifiedName)), 512);
    if (!LooksLikeQualifiedName(qname, 512)) return false;

    // The decisive check: the name string must hash to the value we searched
    // for. Anything that is not genuinely this type fails here.
    if (HashForName(qname) != expectHash) return false;

    const char* shortName = ReadCString(
        reinterpret_cast<const void*>(ReadU64(record, kOffName)), 256);

    out->record        = const_cast<void*>(record);
    out->name          = shortName;
    out->qualifiedName = qname;
    out->size          = ReadU32(record, kOffSize);
    out->fieldCount    = ReadU32(record, kOffFieldCount);
    out->primitiveType = *reinterpret_cast<const uint8_t*>(
                             static_cast<const uint8_t*>(record) + kOffPrimitiveType);
    out->qualifiedHash = expectHash;
    out->internalHash  = ReadU32(record, kOffInternalHash);
    out->valid         = true;
    return true;
}

// Resolve one hash by scanning .rdata. Assumes the caller holds the mutex.
const TypeInfo* ResolveLocked(uint32_t hash) {
    Section rdata{};
    if (!Rdata(&rdata)) return nullptr;

    const auto* bytes = rdata.base;
    const size_t n    = rdata.size;
    if (n < kRecordSize) return nullptr;

    // The hash lives at record+0x50, so the record starts 0x50 bytes earlier.
    // Scanning from kRecordSize keeps every candidate in range.
    const uint8_t needle[4] = {
        static_cast<uint8_t>(hash      ), static_cast<uint8_t>(hash >>  8),
        static_cast<uint8_t>(hash >> 16), static_cast<uint8_t>(hash >> 24),
    };

    for (size_t i = kRecordSize; i + 4 <= n; ++i) {
        if (bytes[i]     != needle[0] || bytes[i + 1] != needle[1] ||
            bytes[i + 2] != needle[2] || bytes[i + 3] != needle[3]) {
            continue;
        }

        const void* candidate = bytes + (i - kOffQualifiedHash);
        static thread_local TypeInfo scratch;
        scratch = TypeInfo{};
        if (LoadRecord(candidate, hash, &scratch)) {
            static thread_local TypeInfo stored;
            stored = scratch;
            return &stored;
        }
    }
    return nullptr;
}

std::mutex g_mutex;
std::unordered_map<uint32_t, TypeInfo> g_types;   // hash -> resolved record
std::unordered_map<uint32_t, std::string> g_names; // hash -> qualified name
uint32_t g_resolved = 0;

} // namespace

uint32_t HashForName(const char* qualifiedName) {
    if (!qualifiedName) return 0;
    uint32_t h = 2166136261u;   // FNV-1a 32 offset basis
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(qualifiedName);
         *p; ++p) {
        h ^= *p;
        h *= 16777619u;         // FNV prime
    }
    return h;
}

const TypeInfo* ByHash(uint32_t hash) {
    if (hash == 0) return nullptr;

    std::lock_guard<std::mutex> lock(g_mutex);

    auto it = g_types.find(hash);
    if (it != g_types.end()) {
        return it->second.valid ? &it->second : nullptr;
    }

    TypeInfo info{};
    if (const TypeInfo* found = ResolveLocked(hash); found) {
        info = *found;
    }
    // Cache negatives too, so a missing type is one scan rather than one per
    // call (a message-flow probe can ask about the same hash many times).
    g_types.emplace(hash, info);
    if (info.valid) {
        ++g_resolved;
        if (info.qualifiedName) g_names.emplace(hash, info.qualifiedName);
    }
    return info.valid ? &g_types[hash] : nullptr;
}

const TypeInfo* ByName(const char* qualifiedName) {
    return ByHash(HashForName(qualifiedName));
}

const Field* FindField(const TypeInfo* type, const char* fieldName) {
    if (!type || !type->valid || !type->record || !fieldName) return nullptr;

    const void* fields = reinterpret_cast<const void*>(
        ReadU64(type->record, kOffStructFields));
    if (!fields || type->fieldCount == 0) return nullptr;

    const size_t tableBytes = size_t(type->fieldCount) * kFieldEntrySize;
    if (!Readable(fields, tableBytes)) return nullptr;

    static thread_local Field out;

    for (uint32_t i = 0; i < type->fieldCount; ++i) {
        const auto* entry = static_cast<const uint8_t*>(fields) + i * kFieldEntrySize;
        const char* name = ReadCString(
            reinterpret_cast<const void*>(ReadU64(entry, kFieldOffName)), 256);
        if (!name || strcmp(name, fieldName) != 0) continue;

        out.name = name;
        out.type = nullptr;
        out.dataOffset = ReadU32(entry, kFieldOffDataOff);

        // Resolve the field's declared type by reading its record's own hash.
        const void* typeRecord = reinterpret_cast<const void*>(
            ReadU64(entry, kFieldOffType));
        if (typeRecord && Readable(typeRecord, kRecordSize)) {
            const uint32_t th = ReadU32(typeRecord, kOffQualifiedHash);
            out.type = ByHash(th);
        }
        return &out;
    }
    return nullptr;
}

const char* NameForHash(uint32_t hash) {
    const TypeInfo* t = ByHash(hash);
    return t ? t->qualifiedName : nullptr;
}

uint32_t ResolvedCount() {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_resolved;
}

} // namespace wolfmount::reflect
