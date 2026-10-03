from pathlib import Path
import re
root=Path(__file__).resolve().parent
base=Path('/Users/himanshu/.claude/skills/design-html/assets/picker-template.html').read_text()
css=(root/'project.css').read_text()
js=(root/'project.js').read_text().replace('__DATA__',(root/'data.json').read_text())
base=base.replace('/* ============ project CSS (edit: components specific to this product) ============ */','/* ============ project CSS (edit: components specific to this product) ============ */\n'+css)
base=re.sub(r'<script id="project">[\s\S]*?</script>',lambda m:'<script id="project">\n'+js+'\n</script>',base)
(root/'src.html').write_text(base)
