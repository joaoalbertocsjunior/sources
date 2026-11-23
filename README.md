# sources-lib

Agnostic sources adapter, JSON-schema M2M interface, and HTTP control library.

## Layers

1. **Sources** — JSON-schema-driven adapter protocol + registry
2. **M2M** — JSON-RPC 2.0 machine-to-machine interface
3. **HTTP Control** — HTTP server mirroring the M2M interface

## Install

```bash
pip install sources-lib
# with schema validation support:
pip install sources-lib[validation]
```

## Quick start

```python
from sources import SourceRegistry, BaseSourceAdapter

class MyAdapter(BaseSourceAdapter):
    config_schema = {"type": "object", "required": ["url"]}

    def sync(self, record, config):
        return [{"url": record.config["url"]}]

registry = SourceRegistry()
registry.register_kind("my", MyAdapter())
record = registry.add("my", config={"url": "https://example.com"})
rows = registry.sync(record.id)
```
