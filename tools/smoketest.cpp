// ============================================================================
//  WolfMount — layer smoke test
//
//  Loads the Vulkan loader directly (vulkan-1.dll), asks it to enumerate
//  instance layer properties, and checks whether our layer is visible and
//  correctly described. This proves the registry + manifest + DLL export
//  chain works WITHOUT launching the game.
//
//  Build:  see tools\build-smoketest.bat
//  Run:    build\smoketest.exe
// ============================================================================

#define VK_USE_PLATFORM_WIN32_KHR
#include <vulkan/vulkan.h>

#include <cstdio>
#include <cstring>
#include <vector>
#include <cstdint>

static int g_fail = 0;

static void Check(bool ok, const char* what) {
    if (ok) {
        std::printf("  PASS  %s\n", what);
    } else {
        std::printf("  FAIL  %s\n", what);
        g_fail++;
    }
}

int main() {
    std::printf("=== WolfMount Vulkan layer smoke test ===\n\n");

    // ---------------------------------------------------------------------
    // 1. The Vulkan loader itself must be present.
    // ---------------------------------------------------------------------
    HMODULE vk = LoadLibraryA("vulkan-1.dll");
    Check(vk != nullptr, "vulkan-1.dll loads");

    if (!vk) {
        std::printf("\nRESULT: FAIL — no Vulkan loader on this system.\n");
        return 1;
    }

    auto vkEnumerateInstanceLayerProperties =
        (PFN_vkEnumerateInstanceLayerProperties)GetProcAddress(
            vk, "vkEnumerateInstanceLayerProperties");
    Check(vkEnumerateInstanceLayerProperties != nullptr,
          "loader exports vkEnumerateInstanceLayerProperties");

    if (!vkEnumerateInstanceLayerProperties) {
        std::printf("\nRESULT: FAIL — loader unusable.\n");
        return 1;
    }

    // ---------------------------------------------------------------------
    // 2. Enumerate every layer the loader can see.
    // ---------------------------------------------------------------------
    uint32_t count = 0;
    VkResult r = vkEnumerateInstanceLayerProperties(&count, nullptr);
    Check(r == VK_SUCCESS, "first vkEnumerateInstanceLayerProperties call");
    Check(count > 0, "loader sees at least one layer");

    std::vector<VkLayerProperties> layers(count);
    r = vkEnumerateInstanceLayerProperties(&count, layers.data());
    Check(r == VK_SUCCESS, "second vkEnumerateInstanceLayerProperties call");

    std::printf("\n  loader reports %u layer(s):\n", count);
    for (uint32_t i = 0; i < count; ++i) {
        std::printf("    - %s (spec %u.%u)\n", layers[i].layerName,
                    VK_API_VERSION_MAJOR(layers[i].specVersion),
                    VK_API_VERSION_MINOR(layers[i].specVersion));
    }

    // ---------------------------------------------------------------------
    // 3. Our layer must be among them.
    // ---------------------------------------------------------------------
    const char* kLayerName = "VK_LAYER_WOLFMOUNT_wolfmount";
    int  ourIndex = -1;
    for (uint32_t i = 0; i < count; ++i) {
        if (std::strcmp(layers[i].layerName, kLayerName) == 0) {
            ourIndex = (int)i;
            break;
        }
    }

    Check(ourIndex >= 0, "VK_LAYER_WOLFMOUNT_wolfmount is visible to the loader");

    if (ourIndex >= 0) {
        VkLayerProperties& ours = layers[ourIndex];
        std::printf("\n  our layer description: \"%s\"\n", ours.description);
        Check(ours.specVersion >= VK_API_VERSION_1_0, "our layer reports a usable spec version");
        Check(std::strstr(ours.description, "WolfMount") != nullptr,
              "our layer description mentions WolfMount");
    }

    // ---------------------------------------------------------------------
    // 4. The layer DLL must be loadable and export the negotiation entry.
    //    We resolve it from the manifest's library_path.
    // ---------------------------------------------------------------------
    const char* manifestPath =
        "E:\\SteamLibrary\\steamapps\\common\\Enshrouded\\"
        "VK_LAYER_WOLFMOUNT_wolfmount.json";

    FILE* f = std::fopen(manifestPath, "rb");
    Check(f != nullptr, "manifest file readable at game dir");
    if (f) {
        char buf[4096] = {0};
        size_t n = std::fread(buf, 1, sizeof(buf) - 1, f);
        std::fclose(f);
        buf[n] = '\0';
        Check(std::strstr(buf, kLayerName) != nullptr, "manifest names the layer");
        Check(std::strstr(buf, "\"type\": \"GLOBAL\"") != nullptr ||
                  std::strstr(buf, "\"type\":\"GLOBAL\"") != nullptr,
              "manifest declares type GLOBAL");
        Check(std::strstr(buf, "wolfmount_layer.dll") != nullptr,
              "manifest points at wolfmount_layer.dll");
        // The "functions" block is OPTIONAL. The loader discovers the
        // negotiation entry point by name via GetProcAddress, which the
        // layer DLL exports. ReShade and the Steam overlay omit it too.
        Check(std::strstr(buf, "VK_LAYER_WOLFMOUNT_wolfmount") != nullptr,
              "manifest names the layer in the layer block");
    }

    HMODULE layer = LoadLibraryA(
        "E:\\SteamLibrary\\steamapps\\common\\Enshrouded\\wolfmount_layer.dll");
    Check(layer != nullptr, "layer DLL loads standalone");

    if (layer) {
        auto negotiate = (void*)GetProcAddress(
            layer, "vkNegotiateLoaderLayerInterfaceVersion");
        Check(negotiate != nullptr,
              "layer exports vkNegotiateLoaderLayerInterfaceVersion");

        auto enumInst = (void*)GetProcAddress(
            layer, "vkEnumerateInstanceLayerProperties");
        Check(enumInst != nullptr,
              "layer exports vkEnumerateInstanceLayerProperties");

        FreeLibrary(layer);
    }

    // ---------------------------------------------------------------------
    std::printf("\n");
    if (g_fail == 0) {
        std::printf("RESULT: PASS — the Vulkan loader can see and load the layer.\n");
        std::printf("Launch Enshrouded and press F8 to open the WolfMount menu.\n");
        return 0;
    } else {
        std::printf("RESULT: FAIL — %d check(s) failed.\n", g_fail);
        return 1;
    }
}
