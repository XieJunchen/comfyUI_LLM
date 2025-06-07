import importlib
import os
import pkgutil

# 动态加载 node 目录下所有节点模块
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

package = __name__
node_pkg = f"{package}.node"

for _, modname, ispkg in pkgutil.iter_modules([os.path.join(os.path.dirname(__file__), 'node')]):
    if not ispkg:
        module = importlib.import_module(f"{node_pkg}.{modname}")
        if hasattr(module, "NODE_CLASS_MAPPINGS"):
            NODE_CLASS_MAPPINGS.update(getattr(module, "NODE_CLASS_MAPPINGS"))
        if hasattr(module, "NODE_DISPLAY_NAME_MAPPINGS"):
            NODE_DISPLAY_NAME_MAPPINGS.update(getattr(module, "NODE_DISPLAY_NAME_MAPPINGS"))

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]