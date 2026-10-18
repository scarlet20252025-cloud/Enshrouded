// ============================================================================
//  WolfMount — in-process Vulkan layer chain test
//
//  Creates a real Vulkan instance with our layer EXPLICITLY enabled, then
//  verifies:
//    1. the loader loads our DLL,
//    2. our vkCreateInstance runs,
//    3. chain-down succeeds and a valid VkInstance comes back,
//    4. the device path works too, and
//    5. destroying everything unwinds cleanly.
//
//  This exercises exactly the code that STACK_OVERFLOWed, but in a process we
//  control, where a failure is a return code instead of a dead game.
//
//  Run with the layer registered (implicit) OR pass the manifest dir so the
//  test can point the loader at it explicitly.
// ============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#define VK_USE_PLATFORM_WIN32_KHR
#include <vulkan/vulkan.h>

#include <cstdio>
#include <cstring>
#include <vector>

static int g_fail = 0;

static void Check(bool ok, const char* what) {
    if (ok) printf("  PASS  %s\n", what);
    else    { printf("  FAIL  %s\n", what); g_fail++; }
}

int main(int argc, char** argv) {
    const char* layerName = "VK_LAYER_WOLFMOUNT_wolfmount";
    bool explicitLayer = (argc > 1 && strcmp(argv[1], "--explicit") == 0);

    printf("=== WolfMount in-process Vulkan layer test ===\n\n");

    // ---- load the loader ---------------------------------------------------
    HMODULE vk = LoadLibraryA("vulkan-1.dll");
    if (!vk) { printf("FAIL  no vulkan-1.dll\n"); return 1; }

    auto getInstanceProcAddr = (PFN_vkGetInstanceProcAddr)
        GetProcAddress(vk, "vkGetInstanceProcAddr");
    if (!getInstanceProcAddr) { printf("FAIL  no vkGetInstanceProcAddr\n"); return 1; }

    auto createInstance = (PFN_vkCreateInstance)
        getInstanceProcAddr(nullptr, "vkCreateInstance");
    auto enumerateLayers = (PFN_vkEnumerateInstanceLayerProperties)
        getInstanceProcAddr(nullptr, "vkEnumerateInstanceLayerProperties");
    if (!createInstance) { printf("FAIL  no vkCreateInstance\n"); return 1; }

    // ---- 1. is our layer visible? -----------------------------------------
    printf("[1] layer visibility\n");
    uint32_t count = 0;
    enumerateLayers(&count, nullptr);
    std::vector<VkLayerProperties> layers(count);
    enumerateLayers(&count, layers.data());

    bool found = false;
    for (auto& l : layers) {
        if (strcmp(l.layerName, layerName) == 0) found = true;
    }
    Check(found, "layer is enumerated by the loader");
    if (!found) {
        printf("\nRESULT: FAIL — layer not registered. Run install.bat.\n");
        return 1;
    }
    printf("      loader sees %u layers\n\n", count);

    // ---- 2. create an instance (this is what crashed) ---------------------
    printf("[2] vkCreateInstance\n");

    VkApplicationInfo app = { VK_STRUCTURE_TYPE_APPLICATION_INFO };
    app.pApplicationName   = "WolfMount layer test";
    app.applicationVersion = 1;
    app.pEngineName        = "none";
    app.engineVersion      = 1;
    app.apiVersion         = VK_API_VERSION_1_1;

    VkInstanceCreateInfo ci = { VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO };
    ci.pApplicationInfo = &app;

    const char* enabled[1];
    if (explicitLayer) {
        enabled[0] = layerName;
        ci.enabledLayerCount   = 1;
        ci.ppEnabledLayerNames = enabled;
        printf("      mode: layer enabled EXPLICITLY\n");
    } else {
        printf("      mode: layer active as GLOBAL implicit layer\n");
    }

    VkInstance instance = VK_NULL_HANDLE;
    VkResult r = createInstance(&ci, nullptr, &instance);
    printf("      vkCreateInstance -> %d\n", (int)r);
    Check(r == VK_SUCCESS, "instance created without recursing or crashing");
    Check(instance != VK_NULL_HANDLE, "instance handle is non-null");

    if (r != VK_SUCCESS) {
        printf("\nRESULT: FAIL — the layer broke instance creation.\n");
        return 1;
    }

    // ---- 3. instance-level function resolution ----------------------------
    printf("\n[3] instance functions\n");
    auto enumPhys = (PFN_vkEnumeratePhysicalDevices)
        getInstanceProcAddr(instance, "vkEnumeratePhysicalDevices");
    Check(enumPhys != nullptr, "vkEnumeratePhysicalDevices resolves through the chain");

    uint32_t devCount = 0;
    if (enumPhys) enumPhys(instance, &devCount, nullptr);
    printf("      physical devices: %u\n", devCount);
    Check(devCount > 0, "at least one physical device is visible");

    // ---- 4. pick a device and create it -----------------------------------
    printf("\n[4] vkCreateDevice\n");
    if (devCount > 0 && enumPhys) {
        std::vector<VkPhysicalDevice> devs(devCount);
        enumPhys(instance, &devCount, devs.data());

        uint32_t qfCount = 0;
        auto getQf = (PFN_vkGetPhysicalDeviceQueueFamilyProperties)
            getInstanceProcAddr(instance, "vkGetPhysicalDeviceQueueFamilyProperties");
        if (getQf) getQf(devs[0], &qfCount, nullptr);

        float prio = 1.0f;
        VkDeviceQueueCreateInfo qci = { VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO };
        qci.queueFamilyIndex = 0;
        qci.queueCount       = 1;
        qci.pQueuePriorities = &prio;

        VkDeviceCreateInfo dci = { VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO };
        dci.queueCreateInfoCount = 1;
        dci.pQueueCreateInfos    = &qci;

        auto createDevice = (PFN_vkCreateDevice)
            getInstanceProcAddr(instance, "vkCreateDevice");

        VkDevice device = VK_NULL_HANDLE;
        if (createDevice) {
            VkResult dr = createDevice(devs[0], &dci, nullptr, &device);
            printf("      vkCreateDevice -> %d\n", (int)dr);
            Check(dr == VK_SUCCESS, "device created through the layer chain");
            Check(device != VK_NULL_HANDLE, "device handle is non-null");

            if (dr == VK_SUCCESS) {
                auto getDeviceProcAddr = (PFN_vkGetDeviceProcAddr)
                    getInstanceProcAddr(instance, "vkGetDeviceProcAddr");
                Check(getDeviceProcAddr != nullptr, "vkGetDeviceProcAddr resolves");
                if (getDeviceProcAddr) {
                    auto present = (PFN_vkQueuePresentKHR)
                        getDeviceProcAddr(device, "vkQueuePresentKHR");
                    Check(present != nullptr, "vkQueuePresentKHR resolves through the chain");
                }

                auto destroyDevice = (PFN_vkDestroyDevice)
                    getInstanceProcAddr(instance, "vkDestroyDevice");
                if (destroyDevice) destroyDevice(device, nullptr);
                printf("      device destroyed\n");
            }
        } else {
            Check(false, "vkCreateDevice resolvable");
        }
    }

    // ---- 5. tear down ------------------------------------------------------
    printf("\n[5] teardown\n");
    auto destroyInstance = (PFN_vkDestroyInstance)
        getInstanceProcAddr(instance, "vkDestroyInstance");
    Check(destroyInstance != nullptr, "vkDestroyInstance resolves");
    if (destroyInstance) {
        destroyInstance(instance, nullptr);
        printf("      instance destroyed\n");
    }

    printf("\n");
    if (g_fail == 0) {
        printf("RESULT: PASS — layer chains down correctly, no recursion\n");
        return 0;
    }
    printf("RESULT: FAIL — %d check(s) failed\n", g_fail);
    return 1;
}
