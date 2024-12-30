from dash_extensions.javascript import  assign
from dash import Dash, html

style_handle = assign("""function(feature, context){
    const {classes, colorscale, style, colorProp} = context.hideout;  // get props from hideout
    const value = feature.properties[colorProp];  // get value the determines the color
    for (let i = 0; i < classes.length; ++i) {
        if (value > classes[i]) {
            style.fillColor = colorscale[i];  // set the fill color according to the class
        }
    }
    return style;
}""")

def get_info(feature=None):
    header = [html.H4("On Time Rating")]
    if not feature:
        return header + [html.P("Hoover over a district")]
    return header + [html.B(feature["properties"]["NTAName"]), html.Br(),
                     "{} minutes off schedule".format(round(feature["properties"]["rolling_avg"],2))]