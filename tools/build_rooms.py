#!/usr/bin/env python3
"""Render Microsoft Bob's source room WMFs and export desktop hit regions.

Uses source room/object placement data, never Windows executables. Format
references: https://github.com/Treeki/robert.js (MIT; robert-license.txt).
"""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import struct

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets" / "rooms"
SOURCE = DEST / "source"
SIZE = (1600, 1200)
SELECTED = [(69,"study","Study"),(64,"family","Family Room"),
            (44,"kitchen","Kitchen"),(37,"attic","Attic"),
            (41,"garage","Garage"),(39,"sun","Sun Room"),
            (43,"kids","Kid's Room"),(66,"safe","Safe"),
            (67,"mouse","Mouse Hole"),(71,"outside","Outside")]
DESTINATIONS = {69:"study",62:"study",64:"family",45:"family",44:"kitchen",
                37:"attic",41:"garage",39:"sun",43:"kids",66:"safe",60:"safe",
                67:"mouse",61:"mouse",71:"outside",80:"sun"}


def rgb(data):
    return QColor(*data[:3])


def render_wmf(data, width, height, primitives=None, text=True):
    """Draw the WMF primitives actually used by the source Bob room assets."""
    if data[:4] != bytes.fromhex("d7cdc69a"):
        raise ValueError("Expected a placeable WMF")
    left, top, right, bottom = struct.unpack_from("<hhhh", data, 6)
    image = QImage(max(1,width), max(1,height), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.translate(0,0)
    p.scale(width/(right-left),height/(bottom-top))
    p.translate(-left,-top)
    base = p.transform()
    p.setPen(QPen(QColor("black"),1))
    p.setBrush(QBrush(QColor("white")))
    objects = []
    state = {"fill":Qt.FillRule.OddEvenFill,"text":QColor("black"),"align":0,
             "point":QPointF(),"bkcolor":QColor("white"),"bkmode":1}
    saved = []

    def add_object(obj):
        try: index=objects.index(None)
        except ValueError: objects.append(obj)
        else: objects[index]=obj

    def draw_path(path):
        # Bob's room format reserves these two fill colors as transparency
        # keys. Clearing the room layer reveals the separate landscape WMF.
        color = p.brush().color()
        keyed = (color.red(), color.green(), color.blue()) in ((245,250,245),(4,4,4))
        if keyed and p.brush().style() != Qt.BrushStyle.NoBrush:
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.drawPath(path)
            p.restore()
            p.save();p.setBrush(Qt.BrushStyle.NoBrush);p.drawPath(path);p.restore()
        else:
            p.drawPath(path)

    pos=40;primitive_index=0
    try:
        while pos+6 <= len(data):
            length,kind=struct.unpack_from("<IH",data,pos)
            if length<3 or pos+2*length>len(data):
                raise ValueError(f"Invalid WMF record at {pos}")
            arg=data[pos+6:pos+2*length];pos+=2*length
            if kind==0: break
            if kind in (0x324,0x325,0x418,0x41B,0x61C,0x538):
                allowed=primitives is None or primitive_index in primitives
                primitive_index+=1
                if not allowed:continue
            if kind==0x521 and not text:continue
            if kind==0x2FA:
                style,x,_=struct.unpack_from("<Hhh",arg)
                pen=QPen(rgb(arg[6:]),max(1,abs(x)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                pen.setStyle({1:Qt.PenStyle.DashLine,2:Qt.PenStyle.DotLine,
                              3:Qt.PenStyle.DashDotLine,4:Qt.PenStyle.DashDotDotLine,
                              5:Qt.PenStyle.NoPen}.get(style&255,Qt.PenStyle.SolidLine))
                add_object(pen)
            elif kind==0x2FC:
                style=struct.unpack_from("<H",arg)[0]
                add_object(QBrush(Qt.BrushStyle.NoBrush) if style==1 else QBrush(rgb(arg[2:])))
            elif kind==0x142:
                dib=arg[4:];header,bw,bh,planes,bits=struct.unpack_from("<IiiHH",dib)
                used=struct.unpack_from("<I",dib,32)[0]
                pixel_offset=14+header+(used or (1<<bits if bits<=8 else 0))*4
                bmp=struct.pack('<2sIHHI',b'BM',14+len(dib),0,0,pixel_offset)+dib
                texture=QImage.fromData(bmp,"BMP")
                if texture.isNull():raise ValueError("Invalid WMF brush bitmap")
                add_object(QBrush(QPixmap.fromImage(texture)))
            elif kind==0x2FB:
                h,w,esc,orient,weight=struct.unpack_from("<5h",arg)
                family=arg[18:].split(b'\0',1)[0].decode('latin1')
                font=QFont(family or "Times New Roman");font.setPixelSize(max(1,abs(h)))
                font.setBold(weight>=600);font.setItalic(bool(arg[10]));font.setUnderline(bool(arg[11]))
                add_object(font)
            elif kind==0x12D:
                index=struct.unpack_from("<H",arg)[0]
                if index<len(objects):
                    obj=objects[index]
                    if isinstance(obj,QPen):p.setPen(obj)
                    elif isinstance(obj,QBrush):p.setBrush(obj)
                    elif isinstance(obj,QFont):p.setFont(obj)
            elif kind==0x1F0:
                index=struct.unpack_from("<H",arg)[0]
                if index<len(objects):objects[index]=None
            elif kind==0x1E:
                p.save();saved.append(copy.copy(state))
            elif kind==0x127:
                if saved:p.restore();state=saved.pop()
            elif kind==0x106:
                state['fill']=Qt.FillRule.OddEvenFill if struct.unpack_from('<H',arg)[0]==1 else Qt.FillRule.WindingFill
            elif kind==0x209:state['text']=rgb(arg)
            elif kind==0x201:state['bkcolor']=rgb(arg)
            elif kind==0x102:state['bkmode']=struct.unpack_from('<H',arg)[0]
            elif kind==0x12E:state['align']=struct.unpack_from('<H',arg)[0]
            elif kind in (0x324,0x325):
                count=struct.unpack_from('<H',arg)[0];points=struct.unpack_from(f'<{count*2}h',arg,2)
                polygon=QPolygonF([QPointF(points[i],points[i+1]) for i in range(0,len(points),2)])
                if kind==0x324:
                    path=QPainterPath();path.setFillRule(state['fill']);path.addPolygon(polygon);path.closeSubpath()
                    draw_path(path)
                else:p.drawPolyline(polygon)
            elif kind==0x538:
                count=struct.unpack_from('<H',arg)[0];sizes=struct.unpack_from(f'<{count}H',arg,2)
                offset=2+count*2;path=QPainterPath();path.setFillRule(state['fill'])
                for size in sizes:
                    pts=struct.unpack_from(f'<{size*2}h',arg,offset);offset+=size*4
                    path.addPolygon(QPolygonF([QPointF(pts[i],pts[i+1]) for i in range(0,len(pts),2)]));path.closeSubpath()
                draw_path(path)
            elif kind in (0x418,0x41B,0x61C):
                vals=struct.unpack_from('<'+'h'*(len(arg)//2),arg)
                b,r,t,l=vals[-4:];rect=QRectF(l,t,r-l,b-t)
                path=QPainterPath()
                if kind==0x418:path.addEllipse(rect)
                elif kind==0x61C:path.addRoundedRect(rect,abs(vals[1])/2,abs(vals[0])/2)
                else:path.addRect(rect)
                draw_path(path)
            elif kind in (0x214,0x213):
                y,x=struct.unpack_from('<hh',arg);point=QPointF(x,y)
                if kind==0x213:p.drawLine(state['point'],point)
                state['point']=point
            elif kind==0x521:
                length=struct.unpack_from('<H',arg)[0]
                text=arg[2:2+length].decode('latin1');y,x=struct.unpack_from('<hh',arg,2+length+(length%2))
                fm=QFontMetricsF(p.font());align=state['align']
                if align&6==6:x-=fm.horizontalAdvance(text)/2
                elif align&2:x-=fm.horizontalAdvance(text)
                if align&24!=24:y+=fm.ascent() if not align&8 else -fm.descent()
                p.save();p.setPen(state['text']);p.drawText(QPointF(x,y),text);p.restore()
            elif kind in (0x104,0x103,0x20B,0x20C):
                # Source files use placeable bounds; explicit map/window
                # records repeat that mapping and need no second transform.
                pass
            else:raise ValueError(f"Unsupported WMF primitive {kind:#x}")
    finally:
        while saved:p.restore();saved.pop()
        p.end()
    return image


def rect_for(obj):
    return [round(obj[k]*SIZE[n%2]/10000,2) for n,k in enumerate(('x','y','w','h'))]


def action_for(app,name):
    action={'clock':'clock','calendar':'calendar','email':'letter','letter_writer':'notes',
            'household_manager':'album','address_book':'bookshelf',
            'financial_guide':'calculator','checkbook':'calculator','geosafari':'window'}.get(app)
    if action:return action
    name=name.lower()
    if any(k in name for k in ('books','paperbacks','encyclopedia')):return 'bookshelf'
    if any(k in name for k in ('computer','drafting','work table','tools')):return 'desk'
    if any(k in name for k in ('box','chest','cabinet')):return 'cabinet'
    if 'easel' in name:return 'album'
    if 'desk blotter' in name:return 'desk'
    return None


def room_objects(original, identifier):
    """Preserve every source object and its source drawing order."""
    yield from enumerate(original['objects'])


def clock_geometry(obj):
    pic=obj['image'];cx=cy=rx=ry=None
    if pic==811:cx,cy,rx,ry=441,-322,18,18
    elif pic==90:cx,cy,rx,ry=317.5,-421.5,20,20
    elif pic==783:cx,cy,rx,ry=147.5,-307.5,22,22
    elif pic==785:cx,cy,rx,ry=517.5,-275.5,26,26
    elif pic==321:cx,cy,rx,ry=241.5,-151,9,13
    if cx is None:return None
    b=(SOURCE/f'{pic}.wmf').read_bytes();l,t,r,bt=struct.unpack_from('<hhhh',b,6)
    x,y,w,h=rect_for(obj)
    result={'kind':'analog','cx':round(x+(cx-l)*w/(r-l),2),'cy':round(y+(cy-t)*h/(bt-t),2),
            'rx':round(rx*w/(r-l),2),'ry':round(ry*h/(bt-t),2)}
    return result


def calendar_geometry(obj):
    # Date panel from the source calendar vector coordinates.
    panel={47:(282,-296,344,-263),87:(235,-184,274,-156)}.get(obj['image'])
    if panel is None:return None
    l,t,r,b=struct.unpack_from('<4h',(SOURCE/f"{obj['image']}.wmf").read_bytes(),6)
    x,y,w,h=rect_for(obj);pl,pt,pr,pb=panel
    return {'rect':[round(x+(pl-l)*w/(r-l),2),round(y+(pt-t)*h/(b-t),2),
                    round((pr-pl)*w/(r-l),2),round((pb-pt)*h/(b-t),2)]}


def validate_graph(rooms):
    targets={room['id']:{h['room'] for h in room['hotspots'] if 'room' in h} for room in rooms}
    for start in targets:
        seen={start};pending=[start]
        while pending:
            for target in targets[pending.pop()]:
                if target not in targets:raise ValueError(f'Unknown door target {target}')
                if target not in seen:seen.add(target);pending.append(target)
        if seen!=set(targets):raise ValueError(f'Rooms unreachable from {start}: {set(targets)-seen}')


def build(data):
    cache={};rooms=[]
    def art(pic,w,h):
        key=(pic,round(w),round(h))
        if key not in cache:cache[key]=render_wmf((SOURCE/f'{pic}.wmf').read_bytes(),key[1],key[2])
        return cache[key]
    names={identifier:name for _,identifier,name in SELECTED}
    for source_id,identifier,name in SELECTED:
        original=data['rooms'][str(source_id)]
        image=QImage(*SIZE,QImage.Format.Format_RGB32);image.fill(QColor('#ffd16b'));p=QPainter(image)
        p.drawImage(QPointF(0,0),art(original['background'],*SIZE))
        hotspots=[];objects=[];clocks=[];calendars=[];pendulum=None
        animated=QImage(*SIZE,QImage.Format.Format_RGB32);animated.fill(QColor('#ffd16b'));ap=QPainter(animated)
        ap.drawImage(QPointF(0,0),art(original['background'],*SIZE))
        for index,obj in room_objects(original,identifier):
            rect=rect_for(obj);x,y,w,h=rect;info=data['pictures'][str(obj['image'])];label=info['name']
            p.drawImage(QRectF(*rect),art(obj['image'],w,h))
            if obj['image']==811:
                # Separate the source brass bob and center suspension from
                # their static foreground chains and weights. No raster edits.
                raw=(SOURCE/'811.wmf').read_bytes();moving={49,50,*range(120,136)}
                base=render_wmf(raw,round(w),round(h),set(range(151))-moving)
                ap.drawImage(QRectF(*rect),base)
                moving_image=render_wmf(raw,round(w),round(h),moving,text=False)
                front=render_wmf(raw,round(w),round(h),set(range(51,120))|set(range(136,151)),text=False)
                moving_image.save(str(DEST/f'{identifier}-pendulum.png'))
                front.save(str(DEST/f'{identifier}-clock-foreground.png'))
                pendulum={'image':f'rooms/{identifier}-pendulum.png',
                          'foreground':f'rooms/{identifier}-clock-foreground.png',
                          'rect':rect,'pivot':[round((441-395)*w/92,2),round((-295+398)*h/273,2)],
                          'angle':4,'period':2.4}
            else:ap.drawImage(QRectF(*rect),art(obj['image'],w,h))
            objects.append({'image':obj['image'],'name':label,'app':obj['app'],'rect':rect,'source':obj})
            if obj['app']=='clock':
                clock=clock_geometry(obj)
                if clock:clocks.append(clock)
            if obj['app']=='calendar':
                calendar=calendar_geometry(obj)
                if calendar:calendars.append(calendar)
            if obj['app']=='background':continue
            action=action_for(obj['app'],label)
            destination=None
            if obj['app']=='door':
                destination=DESTINATIONS.get(obj.get('destination'))
                if destination is None:
                    destination={'safe':'study','mouse':'family','outside':'garage'}.get(identifier,'family')
                # Connect every included room using the existing door artwork.
                destination={('study',3):'kids',('family',3):'kitchen',
                             ('garage',1):'outside',('outside',5):'family'}.get((identifier,index),destination)
                label='Go to '+names[destination]
            if not action and not destination:continue
            if 'hotspot_rect' in obj:x,y,w,h=obj['hotspot_rect']
            # Visible geometry is clipped to the source room canvas.
            right=min(SIZE[0],x+w);bottom=min(SIZE[1],y+h);x=max(0,x);y=max(0,y)
            if right<=x or bottom<=y:continue
            visible=[round(x,2),round(y,2),round(right-x,2),round(bottom-y,2)]
            hot={'id':obj.get('hotspot_id',f'door-{index}' if destination else f'{action}-{index}'), 'label':label,
                 'rect':visible,'normalized':[round(v/SIZE[i%2],6) for i,v in enumerate(visible)],'z':index}
            if destination:hot['room']=destination
            else:hot['action']=action
            hotspots.append(hot)
        p.end();ap.end();image.save(str(DEST/f'{identifier}.png'))
        room={'id':identifier,'sourceId':str(source_id),'name':name,'width':SIZE[0],'height':SIZE[1],
              'image':f'rooms/{identifier}.png','rover':{'x':1200,'y':860,'width':360,'height':300},
              'hotspots':hotspots,'objects':objects,'clocks':clocks,'calendars':calendars}
        if clocks:room['clock']=clocks[0]
        if calendars:room['calendar']=calendars[0]
        if pendulum:
            animated.save(str(DEST/f'{identifier}-animated.png'))
            room['animatedImage']=f'rooms/{identifier}-animated.png';room['pendulum']=pendulum
        rooms.append(room);print(f'Rendered {name}: {len(hotspots)} clickable objects')
    validate_graph(rooms)
    doc={'version':1,'startRoom':'study','source':'Locally imported room data','rooms':rooms}
    (DEST/'rooms.json').write_text(json.dumps(doc,indent=2)+'\n')
    (DEST/'SOURCES.txt').write_text(
        'Microsoft Bob room artwork downloaded separately during setup.\n'
        'Source object coordinates and drawing order retained.\n'
        'Door connections map to the ten included room types.\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if not (SOURCE/'data.json').is_file():
        parser.error('Supply assets/rooms/source/data.json and numbered WMFs locally; see README.txt.')
    data=json.loads((SOURCE/'data.json').read_text())
    app=QApplication.instance() or QApplication([])
    build(data)


if __name__=='__main__':main()
