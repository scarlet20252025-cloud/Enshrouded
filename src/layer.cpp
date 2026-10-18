// ============================================================================
//  WolfMount — Vulkan implicit layer implementation
//
//  This is the technical core of the mod. It intercepts the Vulkan calls the
//  game makes so that we can:
//    1. Draw an ImGui overlay on top of the game frame.
//    2. Subclass the game window to receive raw keyboard input.
//    3. Later: hook game functions to implement the mount.
//
//  Design notes:
//   - We chain down to the next layer / driver for every function we do not
//     care about, so behaviour is unchanged when the overlay is disabled.
//   - Instance-level functions are dispatched through a per-instance dispatch
//     table stored in VkInstance's loader data. Device-level functions go
//     through a per-device table.
// ============================================================================

#define VK_USE_PLATFORM_WIN32_KHR
#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>

#include "layer.h"

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>

#include <atomic>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <mutex>
#include <string>
#include <vector>

// ---------------------------------------------------------------------------
//  ImGui assertions
//
//  IM_ASSERT is redirected by src\wm_imgui_assert.h, which build.bat
//  force-includes into EVERY translation unit. Defining it only here would not
//  reach imgui_impl_vulkan.cpp, and the backend's own asserts would still call
//  abort() — a silent process death with no crash dump.
// ---------------------------------------------------------------------------
#include "wm_imgui_assert.h"

// ---------------------------------------------------------------------------
//  ImGui + backends
// ---------------------------------------------------------------------------
#include "imgui.h"
#include "imgui_impl_vulkan.h"
#include "imgui_impl_win32.h"

// ---------------------------------------------------------------------------
//  ImGui's Win32 message handler forward declaration.
//
//  imgui_impl_win32.h deliberately hides this in an `#if 0` block so the header
//  does not have to pull in <windows.h>; the backend docs say to copy the line
//  into your own .cpp. It must live at FILE SCOPE — inside an anonymous
//  namespace it would get internal linkage and the link would fail.
// ---------------------------------------------------------------------------
extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(
    HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

// ---------------------------------------------------------------------------
//  Mod logic
// ---------------------------------------------------------------------------
#include "mod.h"

// ---------------------------------------------------------------------------
//  Dispatch tables
// ---------------------------------------------------------------------------

namespace {

// Instance dispatch table: filled in when vkCreateInstance is intercepted.
// The Vulkan loader guarantees these are safe to store per-instance.
struct InstanceDispatch {
    VkInstance instance = VK_NULL_HANDLE;

    PFN_vkGetInstanceProcAddr   getInstanceProcAddr   = nullptr;
    PFN_vkGetDeviceProcAddr     getDeviceProcAddr     = nullptr;
    PFN_vkDestroyInstance      destroyInstance       = nullptr;
    PFN_vkCreateDevice         createDevice          = nullptr;
    PFN_vkEnumeratePhysicalDevices enumeratePhysicalDevices = nullptr;
    PFN_vkGetPhysicalDeviceProperties   getPhysicalDeviceProperties   = nullptr;
    PFN_vkGetPhysicalDeviceQueueFamilyProperties getPhysicalDeviceQueueFamilyProperties = nullptr;
    PFN_vkGetPhysicalDeviceMemoryProperties getPhysicalDeviceMemoryProperties = nullptr;
};

struct DeviceDispatch {
    VkDevice   device   = VK_NULL_HANDLE;
    VkInstance instance = VK_NULL_HANDLE;

    PFN_vkGetDeviceProcAddr   getDeviceProcAddr   = nullptr;
    PFN_vkDestroyDevice       destroyDevice       = nullptr;
    PFN_vkGetDeviceQueue      getDeviceQueue      = nullptr;
    PFN_vkQueuePresentKHR     queuePresent        = nullptr;
    PFN_vkQueueSubmit         queueSubmit         = nullptr;
    PFN_vkDeviceWaitIdle      deviceWaitIdle      = nullptr;
    PFN_vkCreateCommandPool   createCommandPool   = nullptr;
    PFN_vkDestroyCommandPool  destroyCommandPool  = nullptr;
    PFN_vkAllocateCommandBuffers allocateCommandBuffers = nullptr;
    PFN_vkFreeCommandBuffers  freeCommandBuffers  = nullptr;
    PFN_vkBeginCommandBuffer  beginCommandBuffer  = nullptr;
    PFN_vkEndCommandBuffer    endCommandBuffer    = nullptr;
    PFN_vkResetCommandBuffer  resetCommandBuffer  = nullptr;
    PFN_vkCreateRenderPass    createRenderPass    = nullptr;
    PFN_vkDestroyRenderPass   destroyRenderPass   = nullptr;
    PFN_vkCreateFramebuffer   createFramebuffer   = nullptr;
    PFN_vkDestroyFramebuffer  destroyFramebuffer  = nullptr;
    PFN_vkCreateImageView     createImageView     = nullptr;
    PFN_vkDestroyImageView    destroyImageView    = nullptr;
    PFN_vkCreateFence         createFence         = nullptr;
    PFN_vkDestroyFence        destroyFence        = nullptr;
    PFN_vkWaitForFences       waitForFences       = nullptr;
    PFN_vkResetFences         resetFences         = nullptr;
    PFN_vkCreateSemaphore     createSemaphore     = nullptr;
    PFN_vkDestroySemaphore    destroySemaphore    = nullptr;
    PFN_vkResetDescriptorPool resetDescriptorPool = nullptr;
    PFN_vkAllocateDescriptorSets allocateDescriptorSets = nullptr;
    PFN_vkFreeDescriptorSets  freeDescriptorSets  = nullptr;
    PFN_vkCreateDescriptorPool createDescriptorPool = nullptr;
    PFN_vkDestroyDescriptorPool destroyDescriptorPool = nullptr;
    PFN_vkResetCommandPool    resetCommandPool    = nullptr;
    PFN_vkCmdBeginRenderPass  cmdBeginRenderPass  = nullptr;
    PFN_vkCmdEndRenderPass    cmdEndRenderPass    = nullptr;
    PFN_vkCreateSwapchainKHR  createSwapchain     = nullptr;
    PFN_vkDestroySwapchainKHR destroySwapchain    = nullptr;
    PFN_vkGetSwapchainImagesKHR getSwapchainImages = nullptr;
};

std::mutex                     g_mutex;
std::vector<InstanceDispatch*> g_instances;
std::vector<DeviceDispatch*>   g_devices;

// The "next" layer, used when we are not the only layer in the chain.
// For a single-layer mod this is the driver itself.
PFN_vkGetInstanceProcAddr g_nextGetInstanceProcAddr = nullptr;
PFN_vkGetDeviceProcAddr   g_nextGetDeviceProcAddr   = nullptr;

// ---------------------------------------------------------------------------
//  Global overlay state
// ---------------------------------------------------------------------------
struct OverlayState {
    bool                initialised   = false;
    bool                initFailed    = false;
    bool                menuVisible   = false;
    HWND                hwnd          = nullptr;
    WNDPROC             origWndProc   = nullptr;

    VkInstance          instance      = VK_NULL_HANDLE;
    VkPhysicalDevice    physDevice    = VK_NULL_HANDLE;
    VkDevice            device        = VK_NULL_HANDLE;
    VkQueue             queue         = VK_NULL_HANDLE;
    uint32_t            queueFamily   = 0;
    VkRenderPass        renderPass    = VK_NULL_HANDLE;
    VkDescriptorPool    descPool      = VK_NULL_HANDLE;
    VkCommandPool       cmdPool       = VK_NULL_HANDLE;
    VkFence             fence         = VK_NULL_HANDLE;
    VkCommandBuffer     cmdBuf        = VK_NULL_HANDLE;

    VkSurfaceKHR        surface       = VK_NULL_HANDLE;
    VkSwapchainKHR      swapchain     = VK_NULL_HANDLE;
    uint32_t            imageCount    = 0;
    std::vector<VkImage>     images;
    std::vector<VkImageView> views;
    std::vector<VkFramebuffer> framebuffers;
    VkExtent2D          extent        = {0, 0};
    VkFormat            format        = VK_FORMAT_UNDEFINED;

    std::vector<VkSemaphore> renderFinished;
    uint32_t                frameIndex = 0;
};

OverlayState g_ov;

// ---------------------------------------------------------------------------
//  Logging — writes next to the DLL so it is easy to find.
//
//  Two paths:
//    * DllMain (below) opens the log the moment the loader loads us, using raw
//      Win32 calls that are safe during DLL_PROCESS_ATTACH.
//    * WM_LOG uses the CRT FILE* once it exists.
//
//  Opening lazily inside WM_LOG alone was not enough: the interesting lines
//  (was vkCreateInstance even called?) happen before any CRT state is ready,
//  and a failure there left us with no log at all.
// ---------------------------------------------------------------------------
FILE* g_log = nullptr;
char  g_logPath[MAX_PATH] = {0};

// Path of this DLL, resolved from an address inside it.
void SelfPath(char* out, size_t n) {
    HMODULE h = nullptr;
    GetModuleHandleExA(
        GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        (LPCSTR)&SelfPath, &h);
    GetModuleFileNameA(h, out, (DWORD)n);
}

// Safe during DllMain: no CRT, no allocation.
void LogOpenRaw() {
    if (g_log) return;

    char path[MAX_PATH] = {0};
    SelfPath(path, MAX_PATH);
    lstrcpynA(g_logPath, path, MAX_PATH);
    lstrcatA(g_logPath, ".log");

    HANDLE h = CreateFileA(g_logPath, GENERIC_WRITE, FILE_SHARE_READ,
                           nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) {
        // Fall back to %TEMP% if the game directory is not writable.
        char tmp[MAX_PATH] = {0};
        GetTempPathA(MAX_PATH, tmp);
        lstrcpynA(g_logPath, tmp, MAX_PATH);
        lstrcatA(g_logPath, "wolfmount_layer.log");
        h = CreateFileA(g_logPath, GENERIC_WRITE, FILE_SHARE_READ,
                        nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (h == INVALID_HANDLE_VALUE) return;
    }

    const char* banner =
        "=== WolfMount layer loaded ===\r\n"
        "If you can read this, the loader loaded the DLL.\r\n";
    DWORD wrote = 0;
    WriteFile(h, banner, (DWORD)lstrlenA(banner), &wrote, nullptr);
    CloseHandle(h);

    // Now let the CRT take over for the rest of the session.
    g_log = fopen(g_logPath, "a");
}

void LogOpen() {
    if (g_log) return;
    LogOpenRaw();
}

#define WM_LOG(...)                            \
    do {                                       \
        if (!g_log) LogOpen();                 \
        if (g_log) {                           \
            fprintf(g_log, __VA_ARGS__);       \
            fputc('\n', g_log);                \
            fflush(g_log);                     \
        }                                      \
    } while (0)

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------
InstanceDispatch* FindInstance(VkInstance inst) {
    for (auto* d : g_instances) if (d->instance == inst) return d;
    return nullptr;
}

DeviceDispatch* FindDevice(VkDevice dev) {
    for (auto* d : g_devices) if (d->device == dev) return d;
    return nullptr;
}

// Vulkan loader stores the dispatch table pointer in the first word of an
// instance/device handle. We use it to reach the next layer's functions.
template <typename T>
void* GetLoaderData(T handle) {
    return *reinterpret_cast<void**>(handle);
}

// ---------------------------------------------------------------------------
//  Window subclassing — raw input capture
//
//  ImGui's Win32 backend needs to SEE the messages to update its input state;
//  it does not poll the OS. If we only forward key events, the mouse never
//  reaches the UI and nothing clickable responds — a scrollbar cannot be
//  dragged because ImGui never learns the cursor moved or that a button is
//  held.
//
//  So every message goes to the backend, and the mod separately decides
//  whether to swallow the input (when the menu is open) so the game does not
//  also react to it.
//
//  ImGui_ImplWin32_WndProcHandler is declared by imgui_impl_win32.h, which is
//  included at the top of this file. Do NOT re-declare it here: a declaration
//  inside this anonymous namespace would create a second, internal-linkage
//  entity and the linker would fail to resolve it.
// ---------------------------------------------------------------------------

LRESULT CALLBACK WndProcHook(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    if (g_ov.initialised) {
        // Let ImGui observe the message first so it can track mouse/key state.
        ImGui_ImplWin32_WndProcHandler(hWnd, msg, wParam, lParam);

        // Ask the mod whether the game should also see this message.
        // Returning true means "the mod consumed it".
        bool consumed = wolfmount::mod::OnWndProc(hWnd, msg, wParam, lParam);

        // Messages that drive ImGui's input but must not reach the game while
        // the menu is open. Everything else falls through untouched.
        if (consumed) {
            switch (msg) {
                case WM_MOUSEMOVE:
                case WM_LBUTTONDOWN: case WM_LBUTTONUP: case WM_LBUTTONDBLCLK:
                case WM_RBUTTONDOWN: case WM_RBUTTONUP: case WM_RBUTTONDBLCLK:
                case WM_MBUTTONDOWN: case WM_MBUTTONUP: case WM_MBUTTONDBLCLK:
                case WM_MOUSEWHEEL:  case WM_MOUSEHWHEEL:
                case WM_XBUTTONDOWN: case WM_XBUTTONUP:
                case WM_KEYDOWN:     case WM_KEYUP:
                case WM_SYSKEYDOWN:  case WM_SYSKEYUP:
                case WM_CHAR:
                    return 0;   // swallow: the game must not act on it
                default:
                    break;
            }
        }
    }
    return CallWindowProcA(g_ov.origWndProc, hWnd, msg, wParam, lParam);
}

void HookWindow(HWND hwnd) {
    if (!hwnd || g_ov.hwnd == hwnd) return;
    g_ov.hwnd = hwnd;
    g_ov.origWndProc = (WNDPROC)SetWindowLongPtrA(
        hwnd, GWLP_WNDPROC, (LONG_PTR)WndProcHook);
    WM_LOG("[wolfmount] subclassed hwnd=%p origWndProc=%p", hwnd, g_ov.origWndProc);
}

// ---------------------------------------------------------------------------
//  Overlay rendering
// ---------------------------------------------------------------------------

// Loader callback for ImGui's Vulkan backend.
//
// ImGui 1.92 resolves its Vulkan entry points at runtime instead of linking
// them. Until ImGui_ImplVulkan_LoadFunctions fills that table, every internal
// call goes through a NULL pointer — which is an ACCESS_VIOLATION the first
// time RenderDrawData runs.
//
// We answer from OUR dispatch chain, so ImGui's calls travel the same path as
// the game's and stay inside the layer.
//
// INSTANCE vs DEVICE MATTERS.
//
// vkGetInstanceProcAddr returns a trampoline for device-level entry points,
// not a real function pointer. Handing that to ImGui while it uses a device we
// created through the layer means the call re-enters the loader with a device
// it does not own, and it faults inside vulkan-1.dll.
//
// That is exactly how the overlay died: ImGui_ImplVulkan_UpdateTexture ->
// ImGui_ImplVulkan_RenderDrawData -> vulkan-1.dll+0x7E591 (ACCESS_VIOLATION)
// on the very first frame, while uploading the font atlas.
//
// So device-level functions are resolved through vkGetDeviceProcAddr, which
// returns a pointer valid for the specific device object.
PFN_vkVoidFunction ImGuiVulkanLoader(const char* functionName, void* userData) {
    (void)userData;
    if (!functionName) return nullptr;

    // Fast path: anything our device dispatch table already holds.
    if (g_ov.device) {
        auto* dd = FindDevice(g_ov.device);
        if (dd && dd->getDeviceProcAddr) {
            PFN_vkVoidFunction f = dd->getDeviceProcAddr(g_ov.device, functionName);
            if (f) return f;
        }
    }

    // Instance-level entry points (vkCreateInstance, vkEnumeratePhysicalDevices,
    // vkGetPhysicalDeviceProperties, ...).
    if (g_nextGetInstanceProcAddr && g_ov.instance) {
        PFN_vkVoidFunction f =
            g_nextGetInstanceProcAddr(g_ov.instance, functionName);
        if (f) return f;
    }

    return nullptr;
}

// ---------------------------------------------------------------------------
//  Font setup
//
//  ImGui ships ProggyClean, which contains ASCII only. Every Chinese string in
//  the mod menu would render as "?????" without a CJK-capable font, so we load
//  one of the fonts Windows already has.
//
//  The ranges cover the CJK punctuation, the main CJK block, and fullwidth
//  forms — enough for the menu labels.
// ---------------------------------------------------------------------------
void LoadMenuFont() {
    ImGuiIO& io = ImGui::GetIO();

    static const char* kCandidates[] = {
        "C:\\Windows\\Fonts\\msyh.ttc",    // Microsoft YaHei
        "C:\\Windows\\Fonts\\msyhl.ttc",   // YaHei Light
        "C:\\Windows\\Fonts\\simhei.ttf",  // SimHei
        "C:\\Windows\\Fonts\\simsun.ttc",  // SimSun
        "C:\\Windows\\Fonts\\deng.ttf",    // DengXian
    };

    ImFontConfig cfg;
    cfg.OversampleH = 1;
    cfg.OversampleV = 1;

    // 0x4E00-0x9FFF  CJK Unified Ideographs
    // 0x3000-0x303F  CJK punctuation
    // 0xFF00-0xFFEF  fullwidth forms
    // 0x2000-0x206F  general punctuation (dashes, quotes)
    static const ImWchar kRanges[] = {
        0x0020, 0x00FF,
        0x2000, 0x206F,
        0x3000, 0x303F,
        0x4E00, 0x9FFF,
        0xFF00, 0xFFEF,
        0,
    };

    for (const char* path : kCandidates) {
        if (GetFileAttributesA(path) == INVALID_FILE_ATTRIBUTES) continue;
        ImFont* f = io.Fonts->AddFontFromFileTTF(path, 17.0f, &cfg, kRanges);
        if (f) {
            WM_LOG("[wolfmount] menu font loaded: %s", path);
            return;
        }
    }

    WM_LOG("[wolfmount] no CJK font found; falling back to the default (ASCII only)");
}

void EnsureImGuiInitialised() {
    if (g_ov.initialised || g_ov.initFailed) return;

    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr;           // do not write imgui.ini into the game dir

    // Keyboard nav is a convenience; the mouse is the primary input.
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;

    // The software cursor is toggled per frame in the render loop, based on
    // whether the menu is open. Leaving it on unconditionally leaves a stray
    // pointer on screen during normal play, because ImGui draws it every frame
    // regardless of whether it has any UI to interact with.
    io.MouseDrawCursor = false;

    // Stop the Win32 backend from calling ShowCursor/SetCursor while the game
    // owns the pointer, which otherwise fights the game's cursor state and can
    // leave the cursor permanently hidden.
    io.ConfigFlags |= ImGuiConfigFlags_NoMouseCursorChange;

    ImGui::StyleColorsDark();

    // Larger, more readable UI: the default font size is cramped at 1080p and
    // the CJK glyphs need the extra height to stay legible.
    ImGui::GetStyle().ScaleAllSizes(1.15f);
    ImGui::GetStyle().WindowRounding = 6.0f;
    ImGui::GetStyle().FrameRounding  = 3.0f;
    ImGui::GetStyle().ScrollbarSize  = 18.0f;   // easier to grab than the default

    // Must run before the backends build their font atlas.
    LoadMenuFont();

    ImGui_ImplWin32_Init(g_ov.hwnd);

    // MUST run before ImGui_ImplVulkan_Init: it populates the backend's
    // internal Vulkan function table. Skipping it means null-pointer calls
    // during the first RenderDrawData.
    if (!ImGui_ImplVulkan_LoadFunctions(
            VK_API_VERSION_1_1, ImGuiVulkanLoader, nullptr)) {
        WM_LOG("[wolfmount] ImGui_ImplVulkan_LoadFunctions FAILED");
        g_ov.initFailed = true;
        return;
    }
    WM_LOG("[wolfmount] ImGui Vulkan function table loaded");

    ImGui_ImplVulkan_InitInfo vi = {};
    vi.ApiVersion      = VK_API_VERSION_1_1;   // REQUIRED, must be non-zero
    vi.Instance        = g_ov.instance;
    vi.PhysicalDevice  = g_ov.physDevice;
    vi.Device          = g_ov.device;
    vi.Queue           = g_ov.queue;
    vi.QueueFamily     = g_ov.queueFamily;

    // Let ImGui create and own its descriptor pool. It needs SAMPLED_IMAGE and
    // SAMPLER descriptors (not COMBINED_IMAGE_SAMPLER); provisioning the pool
    // ourselves with the wrong type breaks descriptor allocation.
    vi.DescriptorPool     = VK_NULL_HANDLE;
    vi.DescriptorPoolSize = 64;   // must be >= IMGUI_IMPL_VULKAN_MINIMUM_SAMPLED_IMAGE_POOL_SIZE

    vi.MinImageCount   = 2;
    vi.ImageCount      = g_ov.imageCount;
    vi.PipelineInfoMain.RenderPass  = g_ov.renderPass;
    vi.PipelineInfoMain.Subpass     = 0;
    vi.PipelineInfoMain.MSAASamples = VK_SAMPLE_COUNT_1_BIT;
    vi.UseDynamicRendering = false;

    WM_LOG("[wolfmount] ImGui_ImplVulkan_Init: instance=%p phys=%p dev=%p queue=%p qf=%u pool=%p rp=%p images=%u",
           (void*)vi.Instance, (void*)vi.PhysicalDevice, (void*)vi.Device,
           (void*)vi.Queue, vi.QueueFamily, (void*)vi.DescriptorPool,
           (void*)vi.PipelineInfoMain.RenderPass, vi.ImageCount);

    if (!ImGui_ImplVulkan_Init(&vi)) {
        WM_LOG("[wolfmount] ImGui_ImplVulkan_Init FAILED");
        g_ov.initFailed = true;
        return;
    }
    WM_LOG("[wolfmount] ImGui_ImplVulkan_Init returned OK");

    wolfmount::mod::OnOverlayReady();
    WM_LOG("[wolfmount] OnOverlayReady returned");

    g_ov.initialised = true;
    WM_LOG("[wolfmount] overlay initialised (imgui %s)", IMGUI_VERSION);
}

void DestroyImGui() {
    if (!g_ov.initialised) return;
    ImGui_ImplVulkan_Shutdown();
    ImGui_ImplWin32_Shutdown();
    ImGui::DestroyContext();
    g_ov.initialised = false;
    WM_LOG("[wolfmount] overlay shut down");
}

// Recreate framebuffers when the swapchain size or the image set changes.
void RebuildFramebuffers() {
    if (!g_ov.swapchain) return;

    VkDevice dev = g_ov.device;
    auto* dd = FindDevice(dev);
    if (!dd) return;

    // Never build views from missing handles: a null image faults inside the
    // driver rather than returning an error. The caller is expected to have
    // filled g_ov.images via vkGetSwapchainImagesKHR first.
    if (g_ov.images.size() != g_ov.imageCount || g_ov.imageCount == 0) {
        WM_LOG("[wolfmount] RebuildFramebuffers: images not ready (%zu vs %u)",
               g_ov.images.size(), g_ov.imageCount);
        return;
    }
    for (auto img : g_ov.images) {
        if (img == VK_NULL_HANDLE) {
            WM_LOG("[wolfmount] RebuildFramebuffers: null swapchain image, skipping");
            return;
        }
    }
    if (!dd->createImageView || !dd->createFramebuffer ||
        !dd->destroyImageView || !dd->destroyFramebuffer) {
        WM_LOG("[wolfmount] RebuildFramebuffers: dispatch incomplete");
        return;
    }

    for (auto fb : g_ov.framebuffers)
        dd->destroyFramebuffer(dev, fb, nullptr);
    g_ov.framebuffers.clear();

    for (auto iv : g_ov.views)
        dd->destroyImageView(dev, iv, nullptr);
    g_ov.views.clear();

    g_ov.views.resize(g_ov.imageCount, VK_NULL_HANDLE);
    g_ov.framebuffers.resize(g_ov.imageCount, VK_NULL_HANDLE);

    for (uint32_t i = 0; i < g_ov.imageCount; ++i) {
        VkImageViewCreateInfo vci = { VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO };
        vci.image    = g_ov.images[i];
        vci.viewType = VK_IMAGE_VIEW_TYPE_2D;
        vci.format   = g_ov.format;
        vci.subresourceRange.aspectMask     = VK_IMAGE_ASPECT_COLOR_BIT;
        vci.subresourceRange.baseMipLevel   = 0;
        vci.subresourceRange.levelCount     = 1;
        vci.subresourceRange.baseArrayLayer = 0;
        vci.subresourceRange.layerCount     = 1;
        VkResult vr = dd->createImageView(dev, &vci, nullptr, &g_ov.views[i]);
        if (vr != VK_SUCCESS) {
            WM_LOG("[wolfmount] createImageView[%u] failed: %d", i, vr);
            g_ov.views[i] = VK_NULL_HANDLE;
            continue;
        }

        VkFramebufferCreateInfo fci = { VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO };
        fci.renderPass  = g_ov.renderPass;
        fci.attachmentCount = 1;
        fci.pAttachments    = &g_ov.views[i];
        fci.width  = g_ov.extent.width;
        fci.height = g_ov.extent.height;
        fci.layers = 1;
        VkResult fr = dd->createFramebuffer(dev, &fci, nullptr, &g_ov.framebuffers[i]);
        if (fr != VK_SUCCESS) {
            WM_LOG("[wolfmount] createFramebuffer[%u] failed: %d", i, fr);
            g_ov.framebuffers[i] = VK_NULL_HANDLE;
        }
    }
}

void DestroyFramebuffers() {
    if (!g_ov.device) return;
    auto* dd = FindDevice(g_ov.device);
    if (!dd) return;
    for (auto fb : g_ov.framebuffers) dd->destroyFramebuffer(g_ov.device, fb, nullptr);
    for (auto iv : g_ov.views)       dd->destroyImageView(g_ov.device, iv, nullptr);
    g_ov.framebuffers.clear();
    g_ov.views.clear();
    g_ov.images.clear();
}

// ---------------------------------------------------------------------------
//  Overlay health
//
//  A Vulkan layer must never take the game down. We cannot rely on SEH here
//  (clang's Windows SEH support does not catch these faults reliably), so we
//  validate every precondition before touching the render path and shut the
//  overlay down permanently on the first sign of trouble.
//
//  The faults this guards against have all been seen for real:
//    * ImGui's Vulkan function table left unpopulated  -> null-pointer call
//    * swapchain images / framebuffers not rebuilt     -> stale handles
//    * the game destroying device objects behind us    -> dangling handles
// ---------------------------------------------------------------------------

// True when every handle the render path dereferences is present.
bool OverlayResourcesReady() {
    if (!g_ov.initialised)      return false;
    if (g_ov.initFailed)        return false;
    if (!g_ov.device)           return false;
    if (!g_ov.queue)            return false;
    if (!g_ov.renderPass)       return false;
    if (!g_ov.cmdBuf)           return false;
    if (!g_ov.fence)            return false;
    if (g_ov.framebuffers.empty()) return false;
    if (g_ov.extent.width == 0 || g_ov.extent.height == 0) return false;
    if (!FindDevice(g_ov.device)) return false;
    return true;
}

// Permanently stop drawing. The game continues untouched.
void DisableOverlay(const char* why) {
    WM_LOG("[wolfmount] *** overlay disabled: %s ***", why);
    g_ov.initialised = false;
    g_ov.initFailed  = true;
}

void RecordAndSubmitWait(VkSemaphore waitOn, VkSemaphore signalWhenDone) {
    if (!OverlayResourcesReady()) return;

    auto* dd = FindDevice(g_ov.device);
    if (!dd) { DisableOverlay("device dispatch missing"); return; }

    // Every function we are about to call must have resolved, or we would be
    // jumping through a null pointer the moment we use it.
    if (!dd->beginCommandBuffer || !dd->endCommandBuffer ||
        !dd->cmdBeginRenderPass  || !dd->cmdEndRenderPass ||
        !dd->queueSubmit         || !dd->waitForFences || !dd->resetFences) {
        DisableOverlay("device dispatch incomplete");
        return;
    }

    ImGui_ImplVulkan_NewFrame();
    ImGui_ImplWin32_NewFrame();
    ImGui::NewFrame();

    // Draw our own pointer only while a panel is up. The game hides the OS
    // cursor, so without this the panel would be clickable but invisible to
    // aim; with it left on permanently, a stray pointer sits over the game.
    ImGui::GetIO().MouseDrawCursor = wolfmount::mod::IsAnyWindowOpen();

    // Poll the hotkeys. The game does not deliver WM_KEYDOWN to its window, so
    // a message-only hotkey never fires during play; reading the key state here
    // works regardless of who consumes the messages.
    wolfmount::mod::PollInput();

    wolfmount::mod::DrawMenu();

    // The console is drawn OUTSIDE DrawMenu on purpose: DrawMenu returns early
    // when the F8 menu is closed, which would leave the F9 console undrawn
    // during normal play.
    wolfmount::mod::DrawConsole();

    ImGui::Render();

    ImDrawData* draw = ImGui::GetDrawData();
    if (!draw) { DisableOverlay("no draw data"); return; }

    dd->resetFences(g_ov.device, 1, &g_ov.fence);

    VkCommandBufferBeginInfo bi = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO };
    bi.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;
    dd->beginCommandBuffer(g_ov.cmdBuf, &bi);

    VkRenderPassBeginInfo rp = { VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO };
    rp.renderPass  = g_ov.renderPass;
    rp.framebuffer = g_ov.framebuffers[g_ov.frameIndex % g_ov.framebuffers.size()];
    rp.renderArea.offset = {0, 0};
    rp.renderArea.extent = g_ov.extent;
    rp.clearValueCount = 0;

    dd->cmdBeginRenderPass(g_ov.cmdBuf, &rp, VK_SUBPASS_CONTENTS_INLINE);
    ImGui_ImplVulkan_RenderDrawData(draw, g_ov.cmdBuf);
    dd->cmdEndRenderPass(g_ov.cmdBuf);

    dd->endCommandBuffer(g_ov.cmdBuf);

    VkSubmitInfo si = { VK_STRUCTURE_TYPE_SUBMIT_INFO };
    si.commandBufferCount = 1;
    si.pCommandBuffers    = &g_ov.cmdBuf;
    si.waitSemaphoreCount = 1;
    si.pWaitSemaphores    = &waitOn;
    VkPipelineStageFlags waitStage = VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;
    si.pWaitDstStageMask  = &waitStage;
    si.signalSemaphoreCount = 1;
    si.pSignalSemaphores    = &signalWhenDone;

    dd->queueSubmit(g_ov.queue, 1, &si, g_ov.fence);
    // The game is about to present using overlayDone, so our submission must
    // have completed. Waiting here is the simple correct approach.
    dd->waitForFences(g_ov.device, 1, &g_ov.fence, VK_TRUE, UINT64_MAX);
    dd->resetFences(g_ov.device, 1, &g_ov.fence);

    g_ov.frameIndex++;

    // Proof of life: the overlay is actually submitting frames. Logged rarely
    // so the file stays readable.
    static uint64_t s_frames = 0;
    if (++s_frames % 120 == 1) {
        WM_LOG("[wolfmount] overlay frame #%llu (swap image %u, %ux%u)",
               (unsigned long long)s_frames,
               g_ov.frameIndex % (uint32_t)g_ov.framebuffers.size(),
               g_ov.extent.width, g_ov.extent.height);
    }
}

// ---------------------------------------------------------------------------
//  Chain-down helpers
//
//  A Vulkan layer receives the next layer's entry points through a
//  VkLayerInstanceCreateInfo / VkLayerDeviceCreateInfo record linked into
//  pCreateInfo->pNext. We MUST walk that chain and pop our own entry
//  (chain_info->u.pLayerInfo = chain_info->u.pLayerInfo->pNext) before calling
//  down, or the loader re-enters us forever.
//
//  Getting this wrong is the classic layer bug and manifests as
//  STACK_OVERFLOW during vkCreateInstance.
// ---------------------------------------------------------------------------

VkLayerInstanceCreateInfo* GetInstanceChainInfo(const VkInstanceCreateInfo* ci) {
    if (!ci) return nullptr;
    auto* link = reinterpret_cast<VkLayerInstanceCreateInfo*>(
        const_cast<void*>(ci->pNext));
    while (link) {
        if (link->sType == VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO &&
            link->function == VK_LAYER_LINK_INFO) {
            return link;
        }
        link = reinterpret_cast<VkLayerInstanceCreateInfo*>(
            const_cast<void*>(link->pNext));
    }
    return nullptr;
}

VkLayerDeviceCreateInfo* GetDeviceChainInfo(const VkDeviceCreateInfo* ci) {
    if (!ci) return nullptr;
    auto* link = reinterpret_cast<VkLayerDeviceCreateInfo*>(
        const_cast<void*>(ci->pNext));
    while (link) {
        if (link->sType == VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO &&
            link->function == VK_LAYER_LINK_INFO) {
            return link;
        }
        link = reinterpret_cast<VkLayerDeviceCreateInfo*>(
            const_cast<void*>(link->pNext));
    }
    return nullptr;
}

// Recursion guard. If any intercepted entry point is entered re-entrantly on
// the same thread we are being called back into ourselves; bail out instead of
// recursing until the stack dies.
thread_local int g_reentryDepth = 0;

struct ReentryGuard {
    bool ok;
    ReentryGuard() {
        ok = (++g_reentryDepth <= 2);
    }
    ~ReentryGuard() { --g_reentryDepth; }
};

} // anonymous namespace

// ---------------------------------------------------------------------------
//  Forward declarations of the intercepted entry points.
//
//  wolfmount_GetInstanceProcAddr / wolfmount_GetDeviceProcAddr are defined
//  above the interceptors but must be able to hand them out by name, so the
//  interceptors are declared here first. They are defined in the anonymous
//  namespace further down and reached only through these declarations.
// ---------------------------------------------------------------------------
namespace {
VKAPI_ATTR VkResult VKAPI_CALL wolfmount_CreateInstance(
    const VkInstanceCreateInfo*, const VkAllocationCallbacks*, VkInstance*);
VKAPI_ATTR void VKAPI_CALL wolfmount_DestroyInstance(
    VkInstance, const VkAllocationCallbacks*);
VKAPI_ATTR VkResult VKAPI_CALL wolfmount_CreateDevice(
    VkPhysicalDevice, const VkDeviceCreateInfo*, const VkAllocationCallbacks*, VkDevice*);
VKAPI_ATTR void VKAPI_CALL wolfmount_DestroyDevice(
    VkDevice, const VkAllocationCallbacks*);
VKAPI_ATTR VkResult VKAPI_CALL wolfmount_CreateSwapchainKHR(
    VkDevice, const VkSwapchainCreateInfoKHR*, const VkAllocationCallbacks*, VkSwapchainKHR*);
VKAPI_ATTR void VKAPI_CALL wolfmount_DestroySwapchainKHR(
    VkDevice, VkSwapchainKHR, const VkAllocationCallbacks*);
VKAPI_ATTR VkResult VKAPI_CALL wolfmount_QueuePresentKHR(
    VkQueue, const VkPresentInfoKHR*);
} // anonymous namespace

// ---------------------------------------------------------------------------
//  Exported dispatch entry points
// ---------------------------------------------------------------------------
extern "C" WM_API PFN_vkVoidFunction VKAPI_CALL wolfmount_GetInstanceProcAddr(
    VkInstance instance, const char* pName)
{
    if (!pName) return nullptr;

    // Hand back OUR internal implementations by name. These are the
    // wolfmount_* functions, never the vulkan-1 import thunks.
    if (!strcmp(pName, "vkGetInstanceProcAddr"))
        return (PFN_vkVoidFunction)wolfmount_GetInstanceProcAddr;
    if (!strcmp(pName, "vkCreateInstance"))
        return (PFN_vkVoidFunction)wolfmount_CreateInstance;
    if (!strcmp(pName, "vkDestroyInstance"))
        return (PFN_vkVoidFunction)wolfmount_DestroyInstance;
    if (!strcmp(pName, "vkCreateDevice"))
        return (PFN_vkVoidFunction)wolfmount_CreateDevice;
    if (!strcmp(pName, "vkDestroyDevice"))
        return (PFN_vkVoidFunction)wolfmount_DestroyDevice;
    if (!strcmp(pName, "vkCreateSwapchainKHR"))
        return (PFN_vkVoidFunction)wolfmount_CreateSwapchainKHR;
    if (!strcmp(pName, "vkDestroySwapchainKHR"))
        return (PFN_vkVoidFunction)wolfmount_DestroySwapchainKHR;
    if (!strcmp(pName, "vkQueuePresentKHR"))
        return (PFN_vkVoidFunction)wolfmount_QueuePresentKHR;

    // Not ours — chain to the next layer or driver.
    if (g_nextGetInstanceProcAddr) {
        return g_nextGetInstanceProcAddr(instance, pName);
    }
    return nullptr; // returning null is legal for unknown instance funcs
}

extern "C" WM_API PFN_vkVoidFunction VKAPI_CALL wolfmount_GetDeviceProcAddr(
    VkDevice device, const char* pName)
{
    if (!pName) return nullptr;

    if (!strcmp(pName, "vkGetDeviceProcAddr"))
        return (PFN_vkVoidFunction)wolfmount_GetDeviceProcAddr;
    if (!strcmp(pName, "vkDestroyDevice"))
        return (PFN_vkVoidFunction)wolfmount_DestroyDevice;
    if (!strcmp(pName, "vkCreateSwapchainKHR"))
        return (PFN_vkVoidFunction)wolfmount_CreateSwapchainKHR;
    if (!strcmp(pName, "vkDestroySwapchainKHR"))
        return (PFN_vkVoidFunction)wolfmount_DestroySwapchainKHR;
    if (!strcmp(pName, "vkQueuePresentKHR"))
        return (PFN_vkVoidFunction)wolfmount_QueuePresentKHR;

    if (g_nextGetDeviceProcAddr) {
        return g_nextGetDeviceProcAddr(device, pName);
    }
    return nullptr;
}

// ---------------------------------------------------------------------------
//  Vectored exception handler
//
//  clang's Windows SEH (__try/__except) does not reliably catch faults here,
//  and ImGui's own IM_ASSERT calls abort(), which terminates the process with
//  no crash dump and no log line. Both make a failure impossible to diagnose.
//
//  A VEH sees every exception before the default handler does, so we log the
//  code and the faulting module+offset. That turns a silent death into a
//  precise location. It is installed for the lifetime of the process.
// ---------------------------------------------------------------------------
PVOID g_veh = nullptr;

// Enumerate the process's loaded modules via a Toolhelp snapshot.
// Declared before DescribeAddress so the latter can use it.
bool EnumProcessModules_ish(HMODULE* out, DWORD* bytesNeeded) {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
    if (snap == INVALID_HANDLE_VALUE) return false;

    MODULEENTRY32 me = {};
    me.dwSize = sizeof(me);
    DWORD count = 0;
    if (Module32First(snap, &me)) {
        do {
            if (count < 64) out[count++] = (HMODULE)me.modBaseAddr;
        } while (Module32Next(snap, &me));
    }
    CloseHandle(snap);
    *bytesNeeded = count * sizeof(HMODULE);
    return count > 0;
}

// Resolve an address to "module+0xoffset" for the log.
void DescribeAddress(void* addr, char* out, size_t n) {
    HMODULE mods[64];
    DWORD needed = 0;
    if (!EnumProcessModules_ish(mods, &needed)) {
        snprintf(out, n, "%p", addr);
        return;
    }
    uintptr_t a = reinterpret_cast<uintptr_t>(addr);
    uintptr_t best = 0;
    HMODULE bestMod = nullptr;
    for (DWORD i = 0; i < needed / sizeof(HMODULE); ++i) {
        uintptr_t base = reinterpret_cast<uintptr_t>(mods[i]);
        if (base <= a && base > best) {
            // Confirm the address falls inside this module by reading its header.
            auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(mods[i]);
            if (!dos || dos->e_magic != IMAGE_DOS_SIGNATURE) continue;
            auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(
                reinterpret_cast<const uint8_t*>(mods[i]) + dos->e_lfanew);
            if (nt->Signature != IMAGE_NT_SIGNATURE) continue;
            uintptr_t end = base + nt->OptionalHeader.SizeOfImage;
            if (a < end) { best = base; bestMod = mods[i]; }
        }
    }
    if (bestMod) {
        char path[MAX_PATH] = {0};
        GetModuleFileNameA(bestMod, path, MAX_PATH);
        const char* leaf = strrchr(path, '\\');
        snprintf(out, n, "%s+0x%llX", leaf ? leaf + 1 : path,
                 (unsigned long long)(a - best));
    } else {
        snprintf(out, n, "%p (unknown module)", addr);
    }
}

LONG CALLBACK VehHandler(EXCEPTION_POINTERS* info) {
    if (!info || !info->ExceptionRecord) return EXCEPTION_CONTINUE_SEARCH;

    DWORD code = info->ExceptionRecord->ExceptionCode;

    // Ignore the non-fatal ones the runtime uses for control flow.
    if (code == 0x406D1388) return EXCEPTION_CONTINUE_SEARCH;   // thread name
    if (code == 0xE06D7363) return EXCEPTION_CONTINUE_SEARCH;   // C++ throw
    if ((code & 0xF0000000) == 0x40000000) return EXCEPTION_CONTINUE_SEARCH; // info

    char where[512] = {0};
    DescribeAddress(info->ExceptionRecord->ExceptionAddress, where, sizeof(where));

    // Dump the faulting instruction bytes. They identify the operation even
    // when the address cannot be attributed to a module (JIT, or an unloaded
    // module whose pages linger).
    unsigned char codeBytes[16] = {0};
    SIZE_T got = 0;
    ReadProcessMemory(GetCurrentProcess(),
                      info->ExceptionRecord->ExceptionAddress,
                      codeBytes, sizeof(codeBytes), &got);

    char hex[64] = {0};
    size_t p = 0;
    for (SIZE_T i = 0; i < got && p + 3 < sizeof(hex); ++i) {
        p += (size_t)snprintf(hex + p, sizeof(hex) - p, "%02X ", codeBytes[i]);
    }

    if (g_log) {
        fprintf(g_log, "[wolfmount] *** EXCEPTION 0x%08lX\n", (unsigned long)code);
        fprintf(g_log, "[wolfmount]     faulting addr : %s\n", where);
        fprintf(g_log, "[wolfmount]     raw address   : %p\n",
                info->ExceptionRecord->ExceptionAddress);
        fprintf(g_log, "[wolfmount]     instr bytes   : %s\n", hex);
        if (code == EXCEPTION_ACCESS_VIOLATION &&
            info->ExceptionRecord->NumberParameters >= 2) {
            const char* kind = "read";
            if (info->ExceptionRecord->ExceptionInformation[0] == 1) kind = "write";
            else if (info->ExceptionRecord->ExceptionInformation[0] == 8) kind = "execute";
            fprintf(g_log, "[wolfmount]     access        : %s at %p\n", kind,
                    (void*)info->ExceptionRecord->ExceptionInformation[1]);
        }
        if (info->ContextRecord) {
            fprintf(g_log, "[wolfmount]     rip=%p rsp=%p rbp=%p\n",
                    (void*)info->ContextRecord->Rip,
                    (void*)info->ContextRecord->Rsp,
                    (void*)info->ContextRecord->Rbp);
            fprintf(g_log, "[wolfmount]     rcx=%p rdx=%p r8=%p r9=%p\n",
                    (void*)info->ContextRecord->Rcx,
                    (void*)info->ContextRecord->Rdx,
                    (void*)info->ContextRecord->R8,
                    (void*)info->ContextRecord->R9);
        }
        fflush(g_log);
    }

    return EXCEPTION_CONTINUE_SEARCH;   // let the game's own handler run
}

// ---------------------------------------------------------------------------
//  DllMain
//
//  Opens the log as early as possible and installs the VEH. The loader calls
//  LoadLibrary on us before it queries any entry point, so this is the first
//  place we can prove we were loaded at all. Everything here uses raw Win32
//  only — the CRT is not safely usable for arbitrary work during
//  DLL_PROCESS_ATTACH, so the VEH is installed on first use instead.
// ---------------------------------------------------------------------------
BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID reserved) {
    (void)hModule; (void)reserved;

    switch (reason) {
        case DLL_PROCESS_ATTACH:
            LogOpenRaw();
            break;
        case DLL_PROCESS_DETACH:
            if (g_veh) { RemoveVectoredExceptionHandler(g_veh); g_veh = nullptr; }
            if (g_log) { fclose(g_log); g_log = nullptr; }
            break;
        default:
            break;
    }
    return TRUE;
}

// Installed lazily from the first intercepted call, when the CRT is usable.
void EnsureVehInstalled() {
    static bool done = false;
    if (done) return;
    done = true;
    g_veh = AddVectoredExceptionHandler(1, VehHandler);
    WM_LOG("[wolfmount] VEH installed: %p", g_veh);
}

// ---------------------------------------------------------------------------
//  Intercepted instance functions
//
//  NAMING IS LOAD-BEARING.
//
//  We link vulkan-1.a (an import library), which DEFINES symbols named exactly
//  vkCreateInstance, vkCreateDevice, vkQueuePresentKHR, ... If our own
//  implementations carried those names, the linker would happily bind the
//  export to the import thunk from vulkan-1.dll instead of to our code, and
//  the loader would end up calling itself through us: unbounded recursion,
//  STACK_OVERFLOW inside vkCreateInstance before any of our logging runs.
//
//  So every intercepted entry point is named wolfmount_*. The loader reaches
//  them only through wolfmount_GetInstanceProcAddr / wolfmount_GetDeviceProcAddr.
// ---------------------------------------------------------------------------
namespace {

VKAPI_ATTR VkResult VKAPI_CALL wolfmount_CreateInstance(
    const VkInstanceCreateInfo* pCreateInfo,
    const VkAllocationCallbacks* pAllocator,
    VkInstance* pInstance)
{
    WM_LOG("[wolfmount] --- vkCreateInstance ---");
    EnsureVehInstalled();

    ReentryGuard guard;
    if (!guard.ok) {
        WM_LOG("[wolfmount] re-entered vkCreateInstance; refusing");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    // -----------------------------------------------------------------------
    //  Chain down: the loader hands us the next layer's GetInstanceProcAddr in
    //  a VkLayerInstanceCreateInfo linked into pCreateInfo->pNext. We must pop
    //  our own link out of the chain before calling down, otherwise the next
    //  layer (or the loader) sees us again and we recurse forever.
    // -----------------------------------------------------------------------
    VkLayerInstanceCreateInfo* chain = GetInstanceChainInfo(pCreateInfo);
    if (!chain || !chain->u.pLayerInfo) {
        WM_LOG("[wolfmount] no loader link info in pNext — not loaded as a layer?");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    PFN_vkGetInstanceProcAddr nextGIPA =
        chain->u.pLayerInfo->pfnNextGetInstanceProcAddr;
    if (!nextGIPA) {
        WM_LOG("[wolfmount] loader gave us a null next GetInstanceProcAddr");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    // Advance the chain past ourselves so we are not re-entered.
    chain->u.pLayerInfo = chain->u.pLayerInfo->pNext;

    g_nextGetInstanceProcAddr = nextGIPA;

    auto nextCreate = (PFN_vkCreateInstance)nextGIPA(nullptr, "vkCreateInstance");
    if (!nextCreate) {
        WM_LOG("[wolfmount] could not resolve next vkCreateInstance");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    VkResult r = nextCreate(pCreateInfo, pAllocator, pInstance);
    if (r != VK_SUCCESS) {
        WM_LOG("[wolfmount] chain-down vkCreateInstance failed: %d", r);
        return r;
    }

    auto* d = new InstanceDispatch();
    d->instance = *pInstance;
    d->getInstanceProcAddr = nextGIPA;
    d->getDeviceProcAddr   = (PFN_vkGetDeviceProcAddr)
        nextGIPA(*pInstance, "vkGetDeviceProcAddr");

    // The Vulkan API capitalises the leading "vk" and each word after it
    // (e.g. vkDestroyInstance), while our struct members use lowerCamelCase.
    // WM_GRAB maps between the two so the call sites read naturally.
    #define WM_GRAB_INST(Name, member) \
        d->member = (PFN_vk##Name)nextGIPA(*pInstance, "vk" #Name)

    WM_GRAB_INST(DestroyInstance,                    destroyInstance);
    WM_GRAB_INST(CreateDevice,                       createDevice);
    WM_GRAB_INST(EnumeratePhysicalDevices,           enumeratePhysicalDevices);
    WM_GRAB_INST(GetPhysicalDeviceProperties,        getPhysicalDeviceProperties);
    WM_GRAB_INST(GetPhysicalDeviceQueueFamilyProperties, getPhysicalDeviceQueueFamilyProperties);
    WM_GRAB_INST(GetPhysicalDeviceMemoryProperties,  getPhysicalDeviceMemoryProperties);
    #undef WM_GRAB_INST
    {
        std::lock_guard<std::mutex> lk(g_mutex);
        g_instances.push_back(d);
    }

    g_ov.instance = *pInstance;
    WM_LOG("[wolfmount] instance created: %p", *pInstance);

    if (!wolfmount::OnInstanceCreated()) {
        WM_LOG("[wolfmount] OnInstanceCreated returned false");
    }

    return VK_SUCCESS;
}

VKAPI_ATTR void VKAPI_CALL wolfmount_DestroyInstance(
    VkInstance instance, const VkAllocationCallbacks* pAllocator)
{
    WM_LOG("[wolfmount] --- vkDestroyInstance ---");
    DestroyImGui();

    InstanceDispatch* d = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_mutex);
        for (auto it = g_instances.begin(); it != g_instances.end(); ++it) {
            if ((*it)->instance == instance) { d = *it; g_instances.erase(it); break; }
        }
    }

    if (d) {
        d->destroyInstance(instance, pAllocator);
        delete d;
    }
}

VKAPI_ATTR VkResult VKAPI_CALL wolfmount_CreateDevice(
    VkPhysicalDevice physicalDevice,
    const VkDeviceCreateInfo* pCreateInfo,
    const VkAllocationCallbacks* pAllocator,
    VkDevice* pDevice)
{
    WM_LOG("[wolfmount] --- vkCreateDevice ---");
    EnsureVehInstalled();

    ReentryGuard guard;
    if (!guard.ok) {
        WM_LOG("[wolfmount] re-entered vkCreateDevice; refusing");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    // Same chain-pop as the instance path, on the device link record.
    VkLayerDeviceCreateInfo* chain = GetDeviceChainInfo(pCreateInfo);
    if (!chain || !chain->u.pLayerInfo) {
        WM_LOG("[wolfmount] no device link info in pNext");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    PFN_vkGetInstanceProcAddr nextGIPA =
        chain->u.pLayerInfo->pfnNextGetInstanceProcAddr;
    PFN_vkGetDeviceProcAddr nextGDPA =
        chain->u.pLayerInfo->pfnNextGetDeviceProcAddr;

    if (!nextGIPA || !nextGDPA) {
        WM_LOG("[wolfmount] device link gave null dispatch pointers");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    chain->u.pLayerInfo = chain->u.pLayerInfo->pNext;

    g_nextGetDeviceProcAddr = nextGDPA;

    // Find the instance that owns this physical device. We track it from
    // vkCreateInstance, which is always called first.
    InstanceDispatch* id = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_mutex);
        if (!g_instances.empty()) id = g_instances.front();
    }
    if (!id) {
        WM_LOG("[wolfmount] vkCreateDevice with no known instance");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    auto nextCreate = (PFN_vkCreateDevice)nextGIPA(id->instance, "vkCreateDevice");
    if (!nextCreate) {
        WM_LOG("[wolfmount] could not resolve next vkCreateDevice");
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    VkDeviceCreateInfo ci = *pCreateInfo;
    VkResult r = nextCreate(physicalDevice, &ci, pAllocator, pDevice);
    if (r != VK_SUCCESS) {
        WM_LOG("[wolfmount] chain-down vkCreateDevice failed: %d", r);
        return r;
    }

    auto* d = new DeviceDispatch();
    d->device   = *pDevice;
    d->instance = id->instance;
    d->getDeviceProcAddr = nextGDPA;

    #define WM_GRAB_DEV(Name, member) \
        d->member = (PFN_vk##Name)nextGDPA(*pDevice, "vk" #Name)

    WM_GRAB_DEV(DestroyDevice,                destroyDevice);
    WM_GRAB_DEV(GetDeviceQueue,               getDeviceQueue);
    WM_GRAB_DEV(QueuePresentKHR,              queuePresent);
    WM_GRAB_DEV(QueueSubmit,                  queueSubmit);
    WM_GRAB_DEV(DeviceWaitIdle,               deviceWaitIdle);
    WM_GRAB_DEV(CreateCommandPool,            createCommandPool);
    WM_GRAB_DEV(DestroyCommandPool,           destroyCommandPool);
    WM_GRAB_DEV(AllocateCommandBuffers,       allocateCommandBuffers);
    WM_GRAB_DEV(FreeCommandBuffers,           freeCommandBuffers);
    WM_GRAB_DEV(BeginCommandBuffer,           beginCommandBuffer);
    WM_GRAB_DEV(EndCommandBuffer,             endCommandBuffer);
    WM_GRAB_DEV(ResetCommandBuffer,           resetCommandBuffer);
    WM_GRAB_DEV(CreateRenderPass,             createRenderPass);
    WM_GRAB_DEV(DestroyRenderPass,            destroyRenderPass);
    WM_GRAB_DEV(CreateFramebuffer,            createFramebuffer);
    WM_GRAB_DEV(DestroyFramebuffer,           destroyFramebuffer);
    WM_GRAB_DEV(CreateImageView,              createImageView);
    WM_GRAB_DEV(DestroyImageView,             destroyImageView);
    WM_GRAB_DEV(CreateFence,                  createFence);
    WM_GRAB_DEV(DestroyFence,                 destroyFence);
    WM_GRAB_DEV(WaitForFences,                waitForFences);
    WM_GRAB_DEV(ResetFences,                  resetFences);
    WM_GRAB_DEV(CreateSemaphore,              createSemaphore);
    WM_GRAB_DEV(DestroySemaphore,             destroySemaphore);
    WM_GRAB_DEV(CreateDescriptorPool,         createDescriptorPool);
    WM_GRAB_DEV(DestroyDescriptorPool,        destroyDescriptorPool);
    WM_GRAB_DEV(ResetCommandPool,             resetCommandPool);
    WM_GRAB_DEV(CmdBeginRenderPass,           cmdBeginRenderPass);
    WM_GRAB_DEV(CmdEndRenderPass,             cmdEndRenderPass);
    WM_GRAB_DEV(ResetDescriptorPool,          resetDescriptorPool);
    WM_GRAB_DEV(AllocateDescriptorSets,       allocateDescriptorSets);
    WM_GRAB_DEV(FreeDescriptorSets,           freeDescriptorSets);
    WM_GRAB_DEV(CreateSwapchainKHR,           createSwapchain);
    WM_GRAB_DEV(DestroySwapchainKHR,          destroySwapchain);
    WM_GRAB_DEV(GetSwapchainImagesKHR,        getSwapchainImages);
    #undef WM_GRAB_DEV

    {
        std::lock_guard<std::mutex> lk(g_mutex);
        g_devices.push_back(d);
    }

    g_ov.device     = *pDevice;
    g_ov.physDevice = physicalDevice;

    // Grab the first queue family that supports graphics.
    uint32_t qfCount = 0;
    id->getPhysicalDeviceQueueFamilyProperties(physicalDevice, &qfCount, nullptr);
    std::vector<VkQueueFamilyProperties> qf(qfCount);
    id->getPhysicalDeviceQueueFamilyProperties(physicalDevice, &qfCount, qf.data());
    for (uint32_t i = 0; i < qfCount; ++i) {
        if (qf[i].queueFlags & VK_QUEUE_GRAPHICS_BIT) {
            g_ov.queueFamily = i;
            break;
        }
    }
    d->getDeviceQueue(*pDevice, g_ov.queueFamily, 0, &g_ov.queue);

    if (!wolfmount::OnDeviceCreated(*pDevice, physicalDevice)) {
        WM_LOG("[wolfmount] OnDeviceCreated returned false");
    }

    WM_LOG("[wolfmount] device created: %p queueFamily=%u", *pDevice, g_ov.queueFamily);
    return VK_SUCCESS;
}

VKAPI_ATTR void VKAPI_CALL wolfmount_DestroyDevice(
    VkDevice device, const VkAllocationCallbacks* pAllocator)
{
    WM_LOG("[wolfmount] vkDestroyDevice");
    DestroyImGui();

    DeviceDispatch* d = nullptr;
    {
        std::lock_guard<std::mutex> lk(g_mutex);
        for (auto it = g_devices.begin(); it != g_devices.end(); ++it) {
            if ((*it)->device == device) { d = *it; g_devices.erase(it); break; }
        }
    }
    if (d) {
        d->destroyDevice(device, pAllocator);
        delete d;
    }
}

VKAPI_ATTR VkResult VKAPI_CALL wolfmount_CreateSwapchainKHR(
    VkDevice device,
    const VkSwapchainCreateInfoKHR* pCreateInfo,
    const VkAllocationCallbacks* pAllocator,
    VkSwapchainKHR* pSwapchain)
{
    auto* d = FindDevice(device);
    if (!d) return VK_ERROR_INITIALIZATION_FAILED;

    // Create the render pass / resources once, sized to the first swapchain.
    if (!g_ov.renderPass) {
        VkRenderPassCreateInfo rp = { VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO };
        VkAttachmentDescription att = {};
        att.format         = pCreateInfo->imageFormat;
        att.samples        = VK_SAMPLE_COUNT_1_BIT;
        att.loadOp         = VK_ATTACHMENT_LOAD_OP_LOAD;   // draw over game output
        att.storeOp        = VK_ATTACHMENT_STORE_OP_STORE;
        att.stencilLoadOp  = VK_ATTACHMENT_LOAD_OP_DONT_CARE;
        att.stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE;
        att.initialLayout  = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;
        att.finalLayout    = VK_IMAGE_LAYOUT_PRESENT_SRC_KHR;

        VkAttachmentReference ref = { 0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
        VkSubpassDescription sub = {};
        sub.pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS;
        sub.colorAttachmentCount = 1;
        sub.pColorAttachments    = &ref;

        rp.attachmentCount = 1;
        rp.pAttachments    = &att;
        rp.subpassCount    = 1;
        rp.pSubpasses      = &sub;

        VkResult rr = d->createRenderPass(device, &rp, nullptr, &g_ov.renderPass);
        if (rr != VK_SUCCESS) {
            WM_LOG("[wolfmount] createRenderPass failed: %d", rr);
            return rr;
        }

        // NOTE: we deliberately do NOT create a descriptor pool here.
        //
        // ImGui 1.92 allocates SAMPLED_IMAGE and SAMPLER descriptors (separate
        // types, not COMBINED_IMAGE_SAMPLER). A pool built with the wrong type
        // makes vkAllocateDescriptorSets fail and the backend then writes
        // through an empty set — an ACCESS_VIOLATION at a low address.
        //
        // Letting ImGui own the pool removes that guesswork entirely: we pass
        // DescriptorPoolSize and leave DescriptorPool null.

        VkCommandPoolCreateInfo cp = { VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO };
        cp.flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT;
        cp.queueFamilyIndex = g_ov.queueFamily;
        d->createCommandPool(device, &cp, nullptr, &g_ov.cmdPool);

        VkCommandBufferAllocateInfo cba = { VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO };
        cba.commandPool = g_ov.cmdPool;
        cba.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        cba.commandBufferCount = 1;
        d->allocateCommandBuffers(device, &cba, &g_ov.cmdBuf);

        VkFenceCreateInfo fc = { VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
        d->createFence(device, &fc, nullptr, &g_ov.fence);

        WM_LOG("[wolfmount] overlay resources created");
    }

    // Find the game window and subclass it.
    if (!g_ov.hwnd) {
        struct EnumData { HWND out; DWORD pid; };
        DWORD pid = GetCurrentProcessId();
        HWND found = nullptr;
        // Use a lambda-free approach with a static for the enumeration.
        struct Local {
            static BOOL CALLBACK Proc(HWND h, LPARAM lp) {
                auto* e = reinterpret_cast<EnumData*>(lp);
                DWORD wpid = 0;
                GetWindowThreadProcessId(h, &wpid);
                if (wpid == e->pid && GetWindow(h, GW_OWNER) == nullptr && IsWindowVisible(h)) {
                    e->out = h;
                    return FALSE;
                }
                return TRUE;
            }
        };
        EnumData ed = { nullptr, pid };
        EnumWindows(Local::Proc, (LPARAM)&ed);
        found = ed.out;
        if (found) HookWindow(found);
    }

    g_ov.format  = pCreateInfo->imageFormat;
    g_ov.extent  = pCreateInfo->imageExtent;

    VkResult r = d->createSwapchain(device, pCreateInfo, pAllocator, pSwapchain);
    if (r != VK_SUCCESS) return r;

    g_ov.swapchain = *pSwapchain;

    // Query the image COUNT, then the images themselves. Fetching only the
    // count leaves g_ov.images full of VK_NULL_HANDLE, and handing a null
    // image to vkCreateImageView faults inside the driver.
    uint32_t count = 0;
    VkResult ir = d->getSwapchainImages(device, *pSwapchain, &count, nullptr);
    if (ir != VK_SUCCESS || count == 0) {
        WM_LOG("[wolfmount] getSwapchainImages(count) failed: %d count=%u", ir, count);
        return VK_SUCCESS;   // swapchain is fine; we just skip the overlay
    }

    g_ov.imageCount = count;
    g_ov.images.resize(count);

    ir = d->getSwapchainImages(device, *pSwapchain, &count, g_ov.images.data());
    if (ir != VK_SUCCESS) {
        WM_LOG("[wolfmount] getSwapchainImages(data) failed: %d", ir);
        g_ov.images.clear();
        return VK_SUCCESS;
    }

    WM_LOG("[wolfmount] swapchain created: %p images=%u %ux%u",
           *pSwapchain, g_ov.imageCount, g_ov.extent.width, g_ov.extent.height);

    // RebuildFramebuffers recreates views/framebuffers from g_ov.images, so it
    // must run after the image handles are real.
    RebuildFramebuffers();
    EnsureImGuiInitialised();

    return VK_SUCCESS;
}

VKAPI_ATTR void VKAPI_CALL wolfmount_DestroySwapchainKHR(
    VkDevice device, VkSwapchainKHR swapchain, const VkAllocationCallbacks* pAllocator)
{
    auto* d = FindDevice(device);
    if (d) d->destroySwapchain(device, swapchain, pAllocator);
    if (swapchain == g_ov.swapchain) {
        DestroyFramebuffers();
        g_ov.swapchain = VK_NULL_HANDLE;
    }
}

VKAPI_ATTR VkResult VKAPI_CALL wolfmount_QueuePresentKHR(
    VkQueue queue, const VkPresentInfoKHR* pPresentInfo)
{
    auto* d = FindDevice(g_ov.device);
    if (!d) return VK_ERROR_INITIALIZATION_FAILED;

    if (g_ov.initialised && g_ov.swapchain && pPresentInfo->waitSemaphoreCount > 0) {

        // Lazily create the semaphore the game will wait on.
        if (g_ov.renderFinished.empty()) {
            for (uint32_t i = 0; i < 4; ++i) {
                VkSemaphore s = VK_NULL_HANDLE;
                VkSemaphoreCreateInfo sci = { VK_STRUCTURE_TYPE_SEMAPHORE_CREATE_INFO };
                d->createSemaphore(g_ov.device, &sci, nullptr, &s);
                g_ov.renderFinished.push_back(s);
            }
        }

        // The game's own wait semaphore is the one that signals "the frame is
        // done rendering". We hand that to the game as its present-wait, and
        // give our overlay submission a fresh one to wait on instead.
        VkSemaphore gameDone = pPresentInfo->pWaitSemaphores[0];
        VkSemaphore overlayDone = g_ov.renderFinished[g_ov.frameIndex % g_ov.renderFinished.size()];

        // Draw the overlay, waiting on the game's completion semaphore. This
        // is a no-op if the overlay has been disabled by a precondition check.
        RecordAndSubmitWait(gameDone, overlayDone);

        // If the overlay turned itself off mid-frame, present the game's frame
        // untouched rather than waiting on a semaphore we never signalled.
        if (!g_ov.initialised) {
            return d->queuePresent(queue, pPresentInfo);
        }

        VkPresentInfoKHR pi = *pPresentInfo;
        pi.pWaitSemaphores    = &overlayDone;
        pi.waitSemaphoreCount = 1;

        return d->queuePresent(queue, &pi);
    }

    return d->queuePresent(queue, pPresentInfo);
}

} // anonymous namespace

// ---------------------------------------------------------------------------
//  wolfmount:: lifecycle
// ---------------------------------------------------------------------------
namespace wolfmount {

bool OnInstanceCreated() {
    LogOpen();
    WM_LOG("[wolfmount] OnInstanceCreated");
    return true;
}

bool OnDeviceCreated(VkDevice device, VkPhysicalDevice physDev) {
    (void)device; (void)physDev;
    WM_LOG("[wolfmount] OnDeviceCreated");
    return true;
}

void OnFrame(VkQueue queue, uint32_t imageIndex) {
    (void)queue;
    (void)imageIndex;
}

VkDevice GetDevice() { return g_ov.device; }

} // namespace wolfmount
