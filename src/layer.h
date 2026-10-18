#pragma once
// ============================================================================
//  WolfMount — Enshrouded Wolf Mount Mod
//  Public layer interface.
// ============================================================================

#define VK_USE_PLATFORM_WIN32_KHR
#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>

#ifdef WOLFMOUNT_EXPORTS
    #define WM_API __declspec(dllexport)
#else
    #define WM_API
#endif

// ----------------------------------------------------------------------------
//  Vulkan layer dispatch entry points (implemented in entry.cpp / layer.cpp)
//
//  These MUST be exported from the DLL. The Vulkan loader resolves them by
//  name after LoadLibrary, so a missing __declspec(dllexport) here means the
//  loader silently fails to find them and the layer never activates.
// ----------------------------------------------------------------------------
#define WM_EXPORT extern "C" __declspec(dllexport)

WM_EXPORT PFN_vkVoidFunction VKAPI_CALL wolfmount_GetInstanceProcAddr(
    VkInstance instance, const char* pName);

WM_EXPORT PFN_vkVoidFunction VKAPI_CALL wolfmount_GetDeviceProcAddr(
    VkDevice device, const char* pName);

// ----------------------------------------------------------------------------
//  Layer lifecycle (implemented in layer.cpp)
// ----------------------------------------------------------------------------
namespace wolfmount {

// Called from the vkCreateInstance chain-down. Returns false on failure.
bool OnInstanceCreated();

// Called from the vkCreateDevice chain-down.
bool OnDeviceCreated(VkDevice device, VkPhysicalDevice physDev);

// Called from vkDestroyInstance / vkDestroyDevice.
void OnShutdown();

// Per-frame hook target, called from the swapchain present wrapper.
void OnFrame(VkQueue queue, uint32_t imageIndex);

// Access the current ImGui-enabled logical device (for overlay rendering).
VkDevice GetDevice();

} // namespace wolfmount
