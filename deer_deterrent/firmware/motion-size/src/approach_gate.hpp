#pragma once
#include <algorithm>
#include <initializer_list>

namespace approach {
constexpr int minimumArea=480; // 10% of the 80x60 analysis grid.
struct Region { int area=0,x=0,y=0,w=0,h=0; };
class Gate {
    Region history[5] = {};
    int count=0;
public:
    void reset() {count=0;}
    int frames() const {return count;}
    int gainPixels() const {return count>1?history[count-1].area-history[0].area:0;}
    int gainPercent() const {return count>1?100*gainPixels()/history[0].area:0;}
    bool update(Region current) {
        if(current.area<48 || current.w<=0 || current.h<=0) {reset();return false;}
        if(count) {
            const auto& previous=history[count-1];
            int overlapW=std::max(0,std::min(previous.x+previous.w,current.x+current.w)-std::max(previous.x,current.x));
            int overlapH=std::max(0,std::min(previous.y+previous.h,current.y+current.h)-std::max(previous.y,current.y));
            // Spatial continuity heuristic, not semantic object tracking.
            int smallerBox=std::min(previous.w*previous.h,current.w*current.h);
            if(overlapW*overlapH*100<smallerBox*30) reset();
        }
        if(count==5) {for(int i=1;i<5;++i) history[i-1]=history[i];count=4;}
        history[count++]=current;
        if(count<5) return false;
        for(int i=2;i<5;++i) if(history[i].area<minimumArea) return false;
        int increases=0;
        for(int i=1;i<5;++i)
            increases+=history[i].area-history[i-1].area>=std::max(5,history[i-1].area/20);
        // Five associated frames, >=25% net growth AND >=2 percentage points
        // of image area; at least two meaningful increases allow mild jitter.
        return gainPixels()>=96 && history[4].area*100>=history[0].area*125 && increases>=2;
    }
};

inline bool selftest() {
    auto region=[](int area,int x=10) {return Region{area,x,10,30,30};};
    Gate gate;
    for(int area : {264,266,270,273,278,280}) if(gate.update(region(area))) return false;
    gate.reset();
    for(int area : {650,650,650,650,650,650}) if(gate.update(region(area))) return false;
    gate.reset();
    for(int area : {800,750,700,650,600}) if(gate.update(region(area))) return false;
    gate.reset();
    for(int area : {500,500,500,800,800}) if(gate.update(region(area))) return false;
    gate.reset();
    bool detected=false;
    for(int area : {500,540,530,590,650}) detected=gate.update(region(area));
    if(!detected) return false; // approach with one small fluctuation
    gate.reset();
    for(int area : {100,140,180,220,260}) if(gate.update(region(area))) return false;
    gate.reset();
    gate.update(region(500));gate.update(region(550));
    gate.update(region(600,50));gate.update(region(650,50));
    if(gate.update(region(700,50))) return false; // unrelated region cannot inherit growth
    gate.update(Region{});
    return gate.frames()==0;
}
}
