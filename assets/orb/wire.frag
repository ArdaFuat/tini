#version 440
layout(location=0) in vec2 uv;
layout(location=1) in float depth;
layout(location=0) out vec4 fragColor;
layout(std140,binding=0) uniform buf {
 mat4 qt_Matrix;
 float qt_Opacity;
 float clock;
 float voice;
 float openness;
 float tintR;
 float tintG;
 float tintB;
 float state;
 float pixelRatio;
};
float wire(vec2 grid, bool diagonals) {
 vec2 cell=fract(grid);
 vec2 deriv=max(fwidth(grid),vec2(.00001));
 vec2 axes=min(cell,1.-cell)/deriv;
 float diagonal=abs(cell.x-cell.y)/length(deriv);
 float distance=min(axes.x,axes.y);
 if(diagonals) distance=min(distance,diagonal);
 return 1.-smoothstep(.05*pixelRatio,.38*pixelRatio,distance);
}
void main() {
 float sparse=wire(uv*vec2(14.,7.),false);
 float detailed=wire(uv*vec2(34.,17.),true);
 float ink=mix(sparse,detailed,smoothstep(.05,.85,openness));
 // Keep rear lines visible and distribute shading over the whole sphere.
 // A narrow transition at depth zero looks like individual lights switching off.
 float alpha=mix(.32,.74,smoothstep(-.75,.75,depth))*ink*qt_Opacity;
 fragColor=vec4(vec3(tintR,tintG,tintB)*alpha,alpha);
}
