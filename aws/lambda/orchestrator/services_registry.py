"""
Service Registry - Dynamic loader for all 75+ advanced services.

Automatically imports and registers all available services with graceful degradation.
If a service has missing dependencies, it's skipped without breaking the system.
"""

import os
import importlib
import inspect
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

# Global service registry
_SERVICES: Dict[str, Any] = {}
_SERVICE_METADATA: Dict[str, Dict[str, Any]] = {}


class ServiceRegistry:
    """Central registry for all PhotoGenius AI services."""

    def __init__(self):
        self.services = _SERVICES
        self.metadata = _SERVICE_METADATA
        self._initialized = False

    def initialize(self) -> None:
        """Load all available services from the current directory."""
        if self._initialized:
            return

        logger.info("🔄 Initializing Service Registry...")
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # List of all service files (excluding handler, registry, and semantic enhancer)
        service_files = [
            f[:-3] for f in os.listdir(current_dir)
            if f.endswith('.py')
            and f not in ('handler.py', 'services_registry.py', 'semantic_prompt_enhancer.py', '__init__.py')
        ]

        loaded_count = 0
        failed_count = 0

        for service_name in service_files:
            try:
                # Try to import the module
                module = importlib.import_module(service_name)

                # Find all classes in the module
                classes = [
                    (name, obj) for name, obj in inspect.getmembers(module)
                    if inspect.isclass(obj) and obj.__module__ == service_name
                ]

                if classes:
                    # Register the first meaningful class found
                    for class_name, class_obj in classes:
                        if not class_name.startswith('_'):
                            self.services[service_name] = class_obj
                            self.metadata[service_name] = {
                                'class_name': class_name,
                                'module': module,
                                'doc': class_obj.__doc__ or 'No documentation',
                                'available': True
                            }
                            loaded_count += 1
                            logger.debug(f"✅ Loaded: {service_name}.{class_name}")
                            break
                else:
                    # Module has no classes, register the module itself
                    self.services[service_name] = module
                    self.metadata[service_name] = {
                        'class_name': None,
                        'module': module,
                        'doc': module.__doc__ or 'No documentation',
                        'available': True
                    }
                    loaded_count += 1
                    logger.debug(f"✅ Loaded module: {service_name}")

            except Exception as e:
                # Service failed to load (missing deps, import errors, etc.)
                self.metadata[service_name] = {
                    'class_name': None,
                    'module': None,
                    'doc': f'Failed to load: {str(e)}',
                    'available': False,
                    'error': str(e)
                }
                failed_count += 1
                logger.debug(f"⚠️ Skipped: {service_name} - {str(e)[:100]}")

        self._initialized = True
        logger.info(f"✅ Service Registry initialized: {loaded_count} loaded, {failed_count} unavailable")

    def get_service(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        if not self._initialized:
            self.initialize()
        return self.services.get(name)

    def is_available(self, name: str) -> bool:
        """Check if a service is available."""
        if not self._initialized:
            self.initialize()
        return self.metadata.get(name, {}).get('available', False)

    def list_services(self, available_only: bool = False) -> List[str]:
        """List all registered services."""
        if not self._initialized:
            self.initialize()
        if available_only:
            return [
                name for name, meta in self.metadata.items()
                if meta.get('available', False)
            ]
        return list(self.metadata.keys())

    def get_metadata(self, name: str) -> Dict[str, Any]:
        """Get metadata for a service."""
        if not self._initialized:
            self.initialize()
        return self.metadata.get(name, {})

    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        if not self._initialized:
            self.initialize()
        total = len(self.metadata)
        available = sum(1 for m in self.metadata.values() if m.get('available', False))
        unavailable = total - available
        return {
            'total_services': total,
            'available': available,
            'unavailable': unavailable,
            'availability_rate': f"{(available/total*100):.1f}%" if total > 0 else "0%"
        }


# Global singleton instance
registry = ServiceRegistry()


# Convenience functions
def get_service(name: str) -> Optional[Any]:
    """Get a service from the registry."""
    return registry.get_service(name)


def is_service_available(name: str) -> bool:
    """Check if a service is available."""
    return registry.is_available(name)


def list_available_services() -> List[str]:
    """List all available services."""
    return registry.list_services(available_only=True)


def get_registry_stats() -> Dict[str, Any]:
    """Get registry statistics."""
    return registry.get_stats()


# Initialize on import
registry.initialize()
