import os
from converter.app.ir.builder import IRBuilder
from converter.app.generators.react.ui.screen_builder import UIScreenBuilder
from converter.app.generators.react.ui.engine import UIEngine
from converter.app.generators.react.themes.exact import ExactTheme

builder = IRBuilder("C:/Users/Afzal/ZCodeProject/converter/outputs/751569c5/.extract/extraction.json")
builder.load()
app = builder.build()

screen_builder = UIScreenBuilder(app)
screens = screen_builder.build_all()

engine = UIEngine("exact", "automatic", app, screens)
theme = ExactTheme()

for presentation in engine.presentations:
    if "UVIS" in presentation.screen_id or "uvis" in presentation.screen_id.lower():
        print("UIPresentation Screen:", presentation.screen_name)
        print("Section Colors:", presentation.section_colors)
        html = theme.render_page(presentation, 'test', '')
        idx = html.find('className="exact-layout-container"')
        print(html[idx:idx+500])
