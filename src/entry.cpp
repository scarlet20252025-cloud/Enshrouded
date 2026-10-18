// ============================================================================
//  WolfMount — Enshrouded Wolf Mount Mod
//  Layer entry point (Vulkan GLOBAL implicit layer)
//
//  Implements vkNegotiateLoaderLayerInterfaceVersion as required by the
//  Vulkan loader, then hands off to the layer implementation.
// ============================================================================

#define VK_USE_PLATFORM_WIN32_KHR
#include <vulkan/vulkan.h>
#include <vulkan/vk_layer.h>

#include "layer.h"

#include <cstdio>
#include <cstring>
#include <cstdint>

// ---------------------------------------------------------------------------
// Required Vulkan layer entry point.
// The loader calls this first to check API version compatibility.
//
// Must be dllexport — the loader resolves it by name via GetProcAddress.
// ---------------------------------------------------------------------------
VKAPI_ATTR VkResult VKAPI_CALL vkNegotiateLoaderLayerInterfaceVersion(
    VkNegotiateLayerInterface* pNegotiateLayerInterface)
{
    if (pNegotiateLayerInterface == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    if (pNegotiateLayerInterface->sType != LAYER_NEGOTIATE_INTERFACE_STRUCT) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    pNegotiateLayerInterface->pfnGetInstanceProcAddr =
        (PFN_vkGetInstanceProcAddr)wolfmount_GetInstanceProcAddr;
    pNegotiateLayerInterface->pfnGetDeviceProcAddr =
        (PFN_vkGetDeviceProcAddr)wolfmount_GetDeviceProcAddr;

    return VK_SUCCESS;
}

// ---------------------------------------------------------------------------
// Optional but conventional: layer enumeration / description entry points.
// The loader looks for these to identify the layer.
// ---------------------------------------------------------------------------
VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceLayerProperties(
    uint32_t*                   pPropertyCount,
    VkLayerProperties*          pProperties)
{
    if (pPropertyCount == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }

    if (pProperties == nullptr) {
        *pPropertyCount = 1;
        return VK_SUCCESS;
    }

    if (*pPropertyCount < 1) {
        *pPropertyCount = 1;
        return VK_INCOMPLETE;
    }

    *pPropertyCount = 1;

    VkLayerProperties* p = &pProperties[0];
    // "VK_LAYER_" prefix is required by the loader spec.
    snprintf(p->layerName, sizeof(p->layerName), "VK_LAYER_WOLFMOUNT_wolfmount");
    p->specVersion      = VK_API_VERSION_1_4;
    p->implementationVersion = 1;
    snprintf(p->description, sizeof(p->description),
             "WolfMount — Enshrouded wolf mount mod");

    return VK_SUCCESS;
}

VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateInstanceExtensionProperties(
    const char*                 pLayerName,
    uint32_t*                   pPropertyCount,
    VkExtensionProperties*      pProperties)
{
    (void)pLayerName;
    if (pPropertyCount == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    *pPropertyCount = 0;
    return VK_SUCCESS;
}

VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateDeviceLayerProperties(
    VkPhysicalDevice            physicalDevice,
    uint32_t*                   pPropertyCount,
    VkLayerProperties*          pProperties)
{
    (void)physicalDevice;
    return vkEnumerateInstanceLayerProperties(pPropertyCount, pProperties);
}

VKAPI_ATTR VkResult VKAPI_CALL vkEnumerateDeviceExtensionProperties(
    VkPhysicalDevice            physicalDevice,
    const char*                 pLayerName,
    uint32_t*                   pPropertyCount,
    VkExtensionProperties*      pProperties)
{
    (void)physicalDevice;
    (void)pLayerName;
    if (pPropertyCount == nullptr) {
        return VK_ERROR_INITIALIZATION_FAILED;
    }
    *pPropertyCount = 0;
    return VK_SUCCESS;
}
