#version 440
layout(location=0) in vec4 qt_Vertex;
layout(location=1) in vec2 qt_MultiTexCoord0;
layout(location=0) out vec2 uv;
layout(location=1) out float depth;
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
void main() {
 uv=qt_MultiTexCoord0;
 float theta=.055+uv.y*(3.14159265359-.11);
 float phi=uv.x*6.28318530718;
 float phase=clock*.6;
 float deformation=mix(.025,(state>1.5 && state<2.5)?.095:(.035+.20*voice),openness);
 float ripple=sin(theta*4.+phase*2.1)*cos(phi*3.-phase*1.3)+.4*sin(phi*5.+theta*3.+phase);
 vec3 v=vec3(sin(theta)*cos(phi),cos(theta),sin(theta)*sin(phi))*(1.+deformation*ripple);
 // A visible turn, including a gentle changing tilt, makes the small sphere
 // read as a moving object instead of stationary lines changing brightness.
 float angle=clock*.32;
 float x=v.x*cos(angle)+v.z*sin(angle);
 float z=-v.x*sin(angle)+v.z*cos(angle);
 float tilt=.24+.16*sin(clock*.24);
 float y=v.y*cos(tilt)+z*sin(tilt);
 z=-v.y*sin(tilt)+z*cos(tilt);
 float scale=(16.+39.*openness)/(1.-z*.11);
 depth=z;
 gl_Position=qt_Matrix*vec4(72.+x*scale,72.+y*scale,0.,1.);
}
