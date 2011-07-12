#! /usr/bin/env py.test
# -*- coding: utf-8 -*-

import pytest, os
if not os.path.isfile('/usr/bin/ploticus'):
    pytest.skip("no ploticus")

from mwlib import timeline

example_script = """ImageSize  = width:800 height:100
PlotArea   = left:65 right:15 bottom:20 top:5
AlignBars  = justify

Colors =
  id:neogene   value:rgb(0.99215,0.8,0.54)
  id:paleogene value:rgb(1,0.7019,0)
  id:cretaceous   value:rgb(0.5,0.764,0.1098)
  id:jurassic      value:rgb(0.302,0.706,0.5) 
  id:triassic    value:rgb(0.403,0.765,0.716) 
  id:permian   value:rgb(0.404,0.776,0.867) 
  id:carboniferous     value:rgb(0.6,0.741,0.855)
  id:devonian  value:rgb(0.6,0.6,0.788)
  id:silurian  value:rgb(0.694,0.447,0.714)
  id:ordovician      value:rgb(0.976,0.506,0.651)
  id:cambrian  value:rgb(0.984,0.5,0.373)
  id:neoproterozoic    value:rgb(0.792,0.647,0.583)
  id:mesoproterozoic    value:rgb(0.867,0.761,0.533)
  id:paleoproterozoic    value:rgb(0.702,0.698,0.369)
  id:eoarchean    value:rgb(0.5,0.565,0.565)   
  id:paleoarchean    value:rgb(0.6,0.592,0.569)   
  id:mesoarchean    value:rgb(0.698,0.65,0.6)   
  id:neoarchean    value:rgb(0.796,0.804,0.784)   
  id:ediacaran     value:rgb(0.918,0.847,0.737)   
  id:cryogenian    value:rgb(0.863,0.671,0.667)
  id:tonian        value:rgb(0.796,0.643,0.424)  
  id:stratherian   value:rgb(1,1,0.8)   # light yellow
  id:calymmian     value:rgb(1,1,0.8)   # light yellow
  id:orosirian     value:rgb(1,1,0.8)   # light yellow
  id:rhyacian      value:rgb(1,1,0.8)   # light yellow
  id:siderian     value:rgb(1,1,0.8)   # light yellow
  id:ectasian      value:rgb(1,1,0.8)   # light yellow
  id:stenian      value:rgb(1,1,0.8)   # light yellow
  id:cenozoic   value:rgb(1,1,0)
  id:mesozoic   value:rgb(0.5,0.6784,0.3176)
  id:paleozoic  value:rgb(0.5,0.7098,0.835)
  id:phanerozoic value:rgb(0.7019,0.886,0.819)
  id:proterozoic value:rgb(0.8,0.85,0.568)
  id:archean   value:rgb(0.6,0.6784,0.6745)
  id:hadean value:rgb(0.4,0.4,0.4)
  id:black  value:black
  id:white  value:white

Period      = from:-4567.17 till:0
TimeAxis    = orientation:horizontal
ScaleMajor  = unit:year increment:500 start:-4500
ScaleMinor  = unit:year increment:100 start:-4500

Define $markred = text:"*" textcolor:red shift:(0,3) fontsize:10

PlotData=
  align:center textcolor:black fontsize:8 mark:(line,black) width:25 shift:(0,-5)

  bar:eon

  at:      0   align:right  $markred
  at:   -542   align:left   $markred shift:(2,3)
  from: -542   till:    0   text:[[Phanerozoic]]  color:phanerozoic   
  from:-2500   till: -542   text:[[Proterozoic]]  color:proterozoic   
  from:-3800   till: -2500  text:[[Archean]]      color:archean   
  from: start  till: -3800  text:[[Hadean]]       color:hadean


  bar:era

  from:  -65.5 till:    0   text:[[Cenozoic|C~z]] shift:(0,1.5)        color:cenozoic        
  from: -251   till:  -65.5 text:[[Mesozoic|Meso~zoic]] shift:(0,1.5)  color:mesozoic        
  from: -542   till: -251 text:[[Paleozoic|Paleo~zoic]] shift:(0,1.5)  color:paleozoic 
  from: -1000  till:  -542  text:[[Neoproterozoic|Neoprote-~rozoic]] shift:(0,1.8) color:neoproterozoic   
  from:-1600   till:  -1000  text:[[Mesoproterozoic]] color:mesoproterozoic  
  from:-2500   till: -1600  text:[[Paleoproterozoic]] color:paleoproterozoic 
  from:-2800   till: -2500  text:[[Neoarchean|Neo-~archean]] shift:(0,1.5)     color:neoarchean       
  from:-3200   till: -2800  text:[[Mesoarchean|Meso-~archean]] shift:(0,1.5)   color:mesoarchean      
  from:-3600   till: -3200  text:[[Paleoarchean|Paleo-~archean]] shift:(0,1.5) color:paleoarchean     
  from:-3800   till: -3600  text:[[Eoarchean|Eoar-~chean]] shift:(0,0.5) color:eoarchean fontsize:6       
  from:start   till: -3800  color:white

  bar:period

  fontsize:6
  from:   -23.03 till:    0    color:neogene
  from:  -65.5 till:   -23.03  color:paleogene
  from: -145.5   till:  -65.5  color:cretaceous
  from: -199.6   till: -145.5  color:jurassic
  from: -251   till: -199.6    color:triassic
  from: -299   till: -251      color:permian
  from: -359.2   till: -299    color:carboniferous
  from: -416 till: -359.2      color:devonian
  from: -443.7 till: -416      color:silurian
  from: -488.3   till: -443.7  color:ordovician
  from: -542   till: -488.3    color:cambrian

  from: -630   till:  -542  text:[[Ediacaran|Ed.]] color:ediacaran
  from: -850   till:  -630  text:[[Cryogenian|Cryo-~genian]] color:cryogenian shift:(0,0.5)
  from: -1000  till:  -850  text:[[Tonian|Ton-~ian]] color:tonian shift:(0,0.5)
  from: -1200  till:  -1000 text:[[Stenian|Ste-~nian]] color:mesoproterozoic shift:(0,0.5)
  from: -1400  till:  -1200 text:[[Ectasian|Ect-~asian]] color:mesoproterozoic shift:(0,0.5)
  from: -1600  till:  -1400 text:[[Calymmian|Calym-~mian]] color:mesoproterozoic shift:(0,0.5)
  from: -1800  till:  -1600 text:[[Statherian|Stath-~erian]] color:paleoproterozoic shift:(0,0.5)
  from: -2050  till:  -1800 text:[[Orosirian|Oro-~sirian]] color:paleoproterozoic shift:(0,0.5)
  from: -2300  till:  -2050 text:[[Rhyacian|Rhy-~acian]] color:paleoproterozoic shift:(0,0.5)
  from: -2500  till:  -2300 text:[[Siderian|Sid-~erian]] color:paleoproterozoic shift:(0,0.5)
  from: start  till:  -2500 color:white
"""

def test_draw_timeline():
    fp = timeline.drawTimeline(example_script)
    print "result in", fp
    assert fp, "no image file created"
    
