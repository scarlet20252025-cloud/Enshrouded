#pragma once
// ============================================================================
//  WolfMount — runtime reflection-table reader
//
//  The shipped `enshrouded.exe` carries a complete, self-describing type
//  database in `.rdata`: 0x90-byte `TypeMetadata` records that name every
//  `keen::*` type, its size, its fields and their offsets. Nothing in this mod
//  hardcodes a field offset that did not come out of that table.
//
//  HOW IT IS LOCATED (no fragile array address required)
//  -----------------------------------------------------
//  A record stores the FNV-1a-32 hash of its qualified type name at +0x50. That
//  4-byte value is essentially unique inside `.rdata`, so a lookup is:
//
//      scan .rdata for the 4-byte hash
//      treat  hit - 0x50  as a candidate record
//      accept it only if  record[+0x50] == hash  and  record[+0x20] resolves
//      to a printable "keen::..." qualified name
//
//  The search is cached, so each distinct type costs one scan and every later
//  lookup is a map hit. Validating instead of trusting means a game update can
//  only make a lookup fail — it can never silently return wrong offsets.
//
//  TypeMetadata record layout (verified against landmarks — `keen::BlobString`
//  size 8, `keen::float3` size 12, `keen::WorldTransform` size 56,
//  `keen::ecs::HitEvent` size 248 with 22 fields):
//
//      +0x00 char* name        +0x08 u32 nameLen
//      +0x10 char* impactName  +0x18 u32 impactNameLen
//      +0x20 char* qualified   +0x28 u32 qualifiedLen
//      +0x30 char* namespace   +0x38 ...
//      +0x40 u32 size          +0x44 u32 alignment
//      +0x48 u32 fieldCount    +0x4C u8  primitiveType
//      +0x50 u32 qualifiedHash +0x54 u32 internalHash
//      +0x58 Field* structFields
//      +0x60 EnumEntry* enumFields
//      +0x70 void* defaultValue +0x78 u32 defaultValueLen
//
//  A struct field entry is 24 bytes: { char* name; u32 nameLen; u32 pad;
//  TypeMetadata* type; u32 dataOffset; u32 pad }.
// ============================================================================

#include <cstdint>

namespace wolfmount::reflect {

struct TypeInfo;
struct Field;

// A struct field: its name, its declared type and its byte offset.
struct Field {
    const char*    name       = nullptr;
    const TypeInfo* type      = nullptr;
    uint32_t       dataOffset = 0;
};

// One type from the table.
struct TypeInfo {
    void*        record       = nullptr;  // the raw metadata, for validation
    const char*  name         = nullptr;  // short name, e.g. "HitEvent"
    const char*  qualifiedName= nullptr;  // "keen::ecs::HitEvent"
    uint32_t     size         = 0;
    uint32_t     fieldCount   = 0;
    uint8_t      primitiveType= 0;
    uint32_t     qualifiedHash= 0;
    uint32_t     internalHash = 0;
    bool         valid        = false;
};

// FNV-1a-32 of a qualified name — the hash the game itself compares against.
uint32_t HashForName(const char* qualifiedName);

// Resolve a type by the FNV-1a-32 hash of its qualified name. The returned
// pointer is stable for the lifetime of the process; `valid` is false when the
// type is not present in this build.
const TypeInfo* ByHash(uint32_t qualifiedHash);

// Resolve a type by qualified name ("keen::ecs::HitEvent").
const TypeInfo* ByName(const char* qualifiedName);

// Field lookup within a struct type. Returns nullptr when absent.
const Field* FindField(const TypeInfo* type, const char* fieldName);

// Name of a hash, or nullptr when unknown. Useful for turning a hash observed
// in a hook into something readable in the log.
const char* NameForHash(uint32_t qualifiedHash);

// Number of distinct types resolved so far (diagnostics only).
uint32_t ResolvedCount();

} // namespace wolfmount::reflect
