#!/usr/bin/env python3
"""
Vue Component Style and Structure Extractor

This script extracts styles, HTML structure, and component information from Vue.js components
to help with migration to Django + HTMX + Alpine.js.

Usage:
    python docs/migration/extract_vue_styles.py [component_name]
    python docs/migration/extract_vue_styles.py GameRow
    python docs/migration/extract_vue_styles.py --all  # Extract all components
    python docs/migration/extract_vue_styles.py --list  # List all components
"""

import re
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ComponentInfo:
    """Information extracted from a Vue component"""

    name: str
    file_path: str
    template: str
    script: str
    styles: List[Dict[str, str]]  # List of style blocks with lang and scoped info
    dependencies: List[str]  # Components imported/used
    props: List[str]
    data: List[str]
    computed: List[str]
    methods: List[str]
    html_structure: str  # Cleaned HTML structure
    css_styles: str  # Combined CSS styles


class VueComponentExtractor:
    """Extract information from Vue.js component files"""

    def __init__(self, components_dir: str = "frontend/src/components"):
        self.components_dir = Path(components_dir)
        self.components = {}

    def find_components(self) -> List[str]:
        """Find all Vue component files"""
        if not self.components_dir.exists():
            return []

        components = []
        for file in self.components_dir.glob("*.vue"):
            components.append(file.stem)
        return sorted(components)

    def extract_component(self, component_name: str) -> Optional[ComponentInfo]:
        """Extract information from a single Vue component"""
        file_path = self.components_dir / f"{component_name}.vue"

        if not file_path.exists():
            print(
                f"Error: Component {component_name}.vue not found in {self.components_dir}"
            )
            return None

        content = file_path.read_text(encoding="utf-8")

        # Extract template
        template_match = re.search(r"<template>(.*?)</template>", content, re.DOTALL)
        template = template_match.group(1).strip() if template_match else ""

        # Extract script
        script_match = re.search(r"<script>(.*?)</script>", content, re.DOTALL)
        script = script_match.group(1).strip() if script_match else ""

        # Extract all style blocks
        styles = []
        style_pattern = r'<style(?:\s+lang="([^"]+)")?(?:\s+scoped)?>(.*?)</style>'
        for match in re.finditer(style_pattern, content, re.DOTALL):
            lang = match.group(1) or "css"
            scoped = "scoped" in match.group(0)
            styles.append(
                {"lang": lang, "scoped": scoped, "content": match.group(2).strip()}
            )

        # Extract component dependencies
        dependencies = []
        import_pattern = r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]"
        for match in re.finditer(import_pattern, script):
            dep_name = match.group(1)
            dep_path = match.group(2)
            if "./" in dep_path or "../" in dep_path:
                dependencies.append(dep_name)

        # Extract props
        props = []
        props_pattern = r"props:\s*\{([^}]+)\}"
        props_match = re.search(props_pattern, script, re.DOTALL)
        if props_match:
            props_content = props_match.group(1)
            # Simple extraction - look for prop names
            prop_names = re.findall(r"(\w+):", props_content)
            props.extend(prop_names)

        # Extract data properties
        data_props = []
        data_pattern = r"data\(\)\s*\{[^}]*return\s*\{([^}]+)\}"
        data_match = re.search(data_pattern, script, re.DOTALL)
        if data_match:
            data_content = data_match.group(1)
            data_names = re.findall(r"(\w+):", data_content)
            data_props.extend(data_names)

        # Extract computed properties
        computed = []
        computed_pattern = r"computed:\s*\{([^}]+)\}"
        computed_match = re.search(computed_pattern, script, re.DOTALL)
        if computed_match:
            computed_content = computed_match.group(1)
            computed_names = re.findall(r"(\w+)\s*\(", computed_content)
            computed.extend(computed_names)

        # Extract methods
        methods = []
        methods_pattern = r"methods:\s*\{([^}]+)\}"
        methods_match = re.search(methods_pattern, script, re.DOTALL)
        if methods_match:
            methods_content = methods_match.group(1)
            method_names = re.findall(r"(\w+)\s*\([^)]*\)", methods_content)
            methods.extend(method_names)

        # Clean HTML structure (remove Vue directives for structure analysis)
        html_structure = self._clean_html_structure(template)

        # Combine CSS styles
        css_styles = self._combine_styles(styles)

        return ComponentInfo(
            name=component_name,
            file_path=str(file_path),
            template=template,
            script=script,
            styles=styles,
            dependencies=dependencies,
            props=props,
            data=data_props,
            computed=computed,
            methods=methods,
            html_structure=html_structure,
            css_styles=css_styles,
        )

    def _clean_html_structure(self, template: str) -> str:
        """Clean HTML structure by removing Vue directives but keeping structure"""
        # Remove v-if, v-for, v-show but keep structure
        cleaned = re.sub(r'v-if="[^"]*"', "", template)
        cleaned = re.sub(r'v-for="[^"]*"', "", cleaned)
        cleaned = re.sub(r'v-show="[^"]*"', "", cleaned)
        cleaned = re.sub(r':key="[^"]*"', "", cleaned)
        cleaned = re.sub(r':class="[^"]*"', "", cleaned)
        # Keep v-model for form analysis
        # Remove other Vue bindings
        cleaned = re.sub(r':\w+="[^"]*"', "", cleaned)
        cleaned = re.sub(r'@\w+="[^"]*"', "", cleaned)
        # Remove Vue template syntax
        cleaned = re.sub(r"\{\{[^}]+\}\}", "{{ value }}", cleaned)
        return cleaned.strip()

    def _combine_styles(self, styles: List[Dict[str, str]]) -> str:
        """Combine all style blocks into a single CSS string"""
        combined = []
        for style in styles:
            lang = style["lang"]
            content = style["content"]
            scoped = style["scoped"]

            if lang == "sass":
                # Convert basic SASS to CSS (simple conversion)
                content = self._sass_to_css(content)

            if scoped:
                combined.append(f"/* Scoped styles from {lang} */\n{content}")
            else:
                combined.append(f"/* Global styles from {lang} */\n{content}")

        return "\n\n".join(combined)

    def _sass_to_css(self, sass_content: str) -> str:
        """Convert basic SASS syntax to CSS"""
        lines = sass_content.split("\n")
        css_lines = []
        indent_level = 0

        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("//"):
                continue

            # Calculate indent
            current_indent = len(line) - len(stripped)
            spaces = current_indent // 2  # Assuming 2-space indent

            # Handle nesting
            if spaces < indent_level:
                # Close previous blocks
                for _ in range(indent_level - spaces):
                    css_lines.append("}")
                indent_level = spaces

            # Convert SASS to CSS
            if ":" in stripped and not stripped.startswith("&"):
                # Property
                css_lines.append("  " * spaces + stripped)
            elif stripped.endswith(":"):
                # Selector
                selector = stripped[:-1].strip()
                if selector.startswith("&"):
                    # Parent selector - flatten
                    selector = selector[1:].strip()
                css_lines.append("  " * spaces + selector + " {")
                indent_level = spaces + 1
            else:
                # Other line
                css_lines.append("  " * spaces + stripped)

        # Close remaining blocks
        for _ in range(indent_level):
            css_lines.append("}")

        return "\n".join(css_lines)

    def generate_migration_report(
        self, component_name: str, output_dir: str = "migration_reports"
    ) -> str:
        """Generate a migration report for a component"""
        info = self.extract_component(component_name)
        if not info:
            return ""

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        report_file = output_path / f"{component_name}_migration.md"

        report = f"""# Migration Report: {component_name}

## Component Information

- **File**: `{info.file_path}`
- **Dependencies**: {', '.join(info.dependencies) if info.dependencies else 'None'}
- **Props**: {', '.join(info.props) if info.props else 'None'}
- **Data Properties**: {', '.join(info.data) if info.data else 'None'}
- **Computed Properties**: {', '.join(info.computed) if info.computed else 'None'}
- **Methods**: {', '.join(info.methods) if info.methods else 'None'}

## HTML Structure

```html
{info.html_structure}
```

## Original Template

```vue
<template>
{info.template}
</template>
```

## Styles

### Style Blocks

"""

        for i, style in enumerate(info.styles, 1):
            report += f"""
#### Style Block {i}

- **Language**: {style['lang']}
- **Scoped**: {style['scoped']}

```{style['lang']}
{style['content']}
```

"""

        report += f"""
### Combined CSS (for Django template)

```css
{info.css_styles}
```

## Migration Notes

### HTML Structure Matching

1. Copy the HTML structure exactly
2. Replace Vue directives:
   - `v-if` → Django template `if` tag
   - `v-for` → Django template `for` tag
   - `v-show` → Alpine.js `x-show`
   - `v-model` → Alpine.js `x-model` or HTML `name` attribute
   - `:key` → Remove (not needed in Django)
   - `@click` → Alpine.js `@click` or HTML `onclick`
   - `router-link` → Django `url` template tag

### Style Migration

1. Copy all styles to Django template
2. Convert SASS to CSS if needed
3. Handle scoped styles (make selectors specific)
4. Test side-by-side with Vue version

### Component Dependencies

"""

        if info.dependencies:
            report += "This component depends on:\n"
            for dep in info.dependencies:
                report += f"- `{dep}` - Migrate this component first\n"
        else:
            report += (
                "No component dependencies (leaf component - good starting point)\n"
            )

        django_template = f"""```django
{{% extends 'beta/base.html' %}}

{{% block title %}}{component_name} - Acclaimed Games{{% endblock %}}

{{% block content %}}
<style>
{info.css_styles}
</style>

{info.html_structure}
{{% endblock %}}
```"""

        report += f"""
## Django Template Example

{django_template}

## Testing Checklist

- [ ] HTML structure matches exactly
- [ ] All styles copied and converted
- [ ] Colors match exactly (use color picker)
- [ ] Fonts match exactly (inspect computed styles)
- [ ] Spacing matches exactly (measure with DevTools)
- [ ] Responsive behavior matches
- [ ] Hover states work
- [ ] Side-by-side comparison with Vue version
"""

        report_file.write_text(report, encoding="utf-8")
        return str(report_file)

    def generate_all_reports(self, output_dir: str = "migration_reports"):
        """Generate migration reports for all components"""
        components = self.find_components()
        reports = []

        for component in components:
            print(f"Extracting {component}...")
            report_path = self.generate_migration_report(component, output_dir)
            if report_path:
                reports.append(report_path)

        return reports


def main():
    extractor = VueComponentExtractor()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            print("Extracting all components...")
            reports = extractor.generate_all_reports()
            print(
                f"\nGenerated {len(reports)} migration reports in docs/migration/migration_reports/"
            )
            for report in reports:
                print(f"  - {report}")
        elif sys.argv[1] == "--list":
            components = extractor.find_components()
            print(f"Found {len(components)} Vue components:")
            for comp in components:
                print(f"  - {comp}")
        else:
            component_name = sys.argv[1]
            print(f"Extracting {component_name}...")
            report_path = extractor.generate_migration_report(component_name)
            if report_path:
                print(f"\nMigration report generated: {report_path}")
            else:
                print(f"Failed to extract {component_name}")
    else:
        print("Vue Component Style Extractor")
        print("\nUsage:")
        print("  python docs/migration/extract_vue_styles.py [component_name]")
        print("  python docs/migration/extract_vue_styles.py GameRow")
        print(
            "  python docs/migration/extract_vue_styles.py --all  # Extract all components"
        )
        print(
            "  python docs/migration/extract_vue_styles.py --list  # List all components"
        )


if __name__ == "__main__":
    main()
