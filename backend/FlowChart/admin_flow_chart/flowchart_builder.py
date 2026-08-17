import json
import uuid

def generate_drawio_xml(nodes, edges, filename):
    xml_template = """<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio" version="26.0.0">
  <diagram name="Page-1">
    <mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
{cells}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""

    cells = []
    
    # Simple Layout Algorithm
    # Group nodes by layers (bfs from nodes with in-degree 0)
    in_degree = {n['id']: 0 for n in nodes}
    for e in edges:
        in_degree[e['target']] = in_degree.get(e['target'], 0) + 1
        
    layers = []
    current_layer = [n['id'] for n in nodes if in_degree[n['id']] == 0]
    visited = set(current_layer)
    
    while current_layer:
        layers.append(current_layer)
        next_layer = []
        for n_id in current_layer:
            for e in edges:
                if e['source'] == n_id and e['target'] not in visited:
                    visited.add(e['target'])
                    next_layer.append(e['target'])
        current_layer = next_layer
        
    # Handle unconnected nodes
    unvisited = [n['id'] for n in nodes if n['id'] not in visited]
    if unvisited:
        layers.append(unvisited)
        
    positions = {}
    y_offset = 50
    for layer in layers:
        x_offset = 50
        for n_id in layer:
            positions[n_id] = (x_offset, y_offset)
            x_offset += 250
        y_offset += 150
        
    # Node Styles
    styles = {
        'start_end': 'ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;',
        'io': 'shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;fillColor=#dae8fc;strokeColor=#6c8ebf;',
        'process': 'rounded=0;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;',
        'decision': 'rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;',
        'env': 'rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor=#e1d5e7;strokeColor=#9673a6;'
    }
    
    # Add Nodes
    for n in nodes:
        shape = n.get('shape', 'process')
        style = styles.get(shape, styles['process'])
        x, y = positions.get(n['id'], (0,0))
        width = n.get('width', 160)
        height = n.get('height', 60)
        if 'width' not in n:
            if shape == 'start_end':
                width = 100
            elif shape == 'decision':
                height = 80
                width = 180
            
        label = str(n.get('label', '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '&#xa;')
        cell = f'        <mxCell id="{n["id"]}" value="{label}" style="{style}" vertex="1" parent="1">\n'
        cell += f'          <mxGeometry x="{x}" y="{y}" width="{width}" height="{height}" as="geometry" />\n'
        cell += f'        </mxCell>'
        cells.append(cell)
        
    # Add Edges
    for idx, e in enumerate(edges):
        e_id = f"edge_{idx}"
        label = str(e.get('label', '')).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '&#xa;')
        style = 'edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;'
        cell = f'        <mxCell id="{e_id}" value="{label}" style="{style}" edge="1" parent="1" source="{e["source"]}" target="{e["target"]}">\n'
        cell += f'          <mxGeometry relative="1" as="geometry" />\n'
        cell += f'        </mxCell>'
        cells.append(cell)
        
    xml_content = xml_template.replace('{cells}', '\n'.join(cells))
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    print(f"Generated {filename}")

if __name__ == '__main__':
    print("Builder ready")
