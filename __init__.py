from .nodes.zimage_turbo_region_builder import ZImageTurboRegionBuilderKJ

NODE_CLASS_MAPPINGS = {
    "ZImageTurboRegionBuilderKJ": ZImageTurboRegionBuilderKJ,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ZImageTurboRegionBuilderKJ": "Z-Image-Turbo Region Builder KJ",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
