import os
from converter.app.ir.builder import IRBuilder
from converter.app.generators.react.ui.screen_builder import ScreenBuilder
from converter.app.generators.react.ui.engine import UITransformationEngine
from converter.app.generators.react.themes.exact import ExactLayoutTheme

builder = IRBuilder('C:/Users/Afzal/ZCodeProject/converter/outputs/646dbe8a/.extract/extraction.json')
builder.load()
app = builder.build()

screen_builder = ScreenBuilder(app)
screens = screen_builder.build_all()

engine = UITransformationEngine('exact', 'automatic', app, screens)
theme = ExactLayoutTheme()

for presentation in engine.presentations:
    if 'UVIS' in presentation.screen_id or 'uvis' in presentation.screen_id.lower():
        print('UIPresentation Screen:', presentation.screen_name)
        print('Section Colors:', getattr(presentation, 'section_colors', 'MISSING!'))
        html = theme.render_form_page(presentation, 'test', 'TestApi', '')
        idx = html.find('className="exact-layout-container"')
        print(html[idx:idx+500])
