// Parametric enclosure for a deer repellent system
// Units: mm. Open in OpenSCAD; set part to "body", "lid", or "assembly".

part = "assembly"; // [assembly, body, lid]

// Overall envelope (8 x 5 x 3.5 in from the supplied concept diagram)
case_length = 175.5;   // X: 159.5 mm board + 5 mm clearance at each end + 3 mm walls
case_height = 36.0;    // Z: PIR opening has 6.5 mm margins above and below
case_depth = 127.0;    // Y: 5 in
wall = 3.0;
lid_thickness = 3.0;
corner_radius = 4.0;
clearance = 0.35;

// Internal electronics
board_length = 159.5;
board_width = 49.0;
board_thickness = 1.6;
board_x = 8.0;
board_y = 39.0;
board_z = 55.0;
support_height = 6.0;
support_diameter = 7.0;
support_spacing_x = 145.0;
support_spacing_y = 35.0;

// Yard-side openings. Coordinates are measured from the left and bottom.
buzzer_x = 24.0;
buzzer_z = 18.0;
buzzer_diameter = 16.0;
grille_slot_width = 1.6;
grille_slot_pitch = 3.2;
grille_slot_count = 5;

led_x = 66.0;
led_z = 18.0;
led_diameter = 5.0;
led_shade_width = 22.0;
led_shade_height = 17.0;
led_shade_projection = 8.0;

camera_x = 109.0;
camera_z = 18.0;
camera_mount_size = 8.5;
camera_hole_diameter = 4.0; // retained for optional lens-only variant
camera_shade_projection = 8.0;

pir_x = 152.0;
pir_z = 18.0;
pir_square = 23.0; // 2.3 cm sensor section that protrudes
pir_dome_diameter = 23.0; // adjust to the actual Fresnel dome diameter
pir_hood_projection = 10.0;

// Status light opening on the upper side wall.
status_x = case_length * 0.74;
status_width = 22.0;
status_depth = 4.0;

// Lid fasteners
lid_screw_diameter = 3.2;
boss_diameter = 8.0;
boss_height = 7.0;
fastener_inset = 6.0;
dowel_diameter = 12.7;          // 0.5 in dowel
dowel_socket_clearance = 0.8;   // diametral clearance for a printed fit
dowel_socket_height = 15.0;
dowel_socket_roof = 3.0;
dowel_socket_taper = 3.0;
dowel_socket_spacing = 80.0;

$fn = 128; // smooth circular openings and dowel sockets in exported meshes

module rounded_box(size, r) {
    // Rounded vertical corners while keeping the top and bottom faces flat.
    hull() for (x=[r,size[0]-r], y=[r,size[1]-r])
        translate([x,y,0]) cylinder(h=size[2], r=r);
}

module shell_body() {
    difference() {
        rounded_box([case_length,case_depth,case_height], corner_radius);
        // Main cavity open at the top; the removable lid closes this opening.
        translate([wall,wall,wall])
            cube([case_length-2*wall,case_depth-2*wall,case_height-wall+0.2]);

        // Yard-facing panel openings (front is Y=0).
        // Buzzer grille: five narrow slots sized within the 16 mm transducer footprint.
        for (i=[0:grille_slot_count-1])
            translate([buzzer_x-(grille_slot_count-1)*grille_slot_pitch/2+i*grille_slot_pitch,
                       -0.1, buzzer_z-(buzzer_diameter+2)/2])
                cube([grille_slot_width,wall+0.2,buzzer_diameter+2]);

        // LED aperture
        translate([led_x,-0.1,led_z]) rotate([-90,0,0])
            cylinder(h=wall+0.2,d=led_diameter+2*clearance);

        // Square camera mounting footprint (8.5 mm) through the yard-side wall.
        translate([camera_x-camera_mount_size/2,-0.1,camera_z-camera_mount_size/2])
            cube([camera_mount_size,wall+0.2,camera_mount_size]);

        // PIR sensor square aperture
        translate([pir_x-pir_square/2,-0.1,pir_z-pir_square/2])
            cube([pir_square,wall+0.2,pir_square]);

        // Recessed status light opening on the upper side wall.
        translate([status_x,case_depth-wall-status_depth,case_height-wall-0.1])
            cube([status_width,status_depth,wall+0.2]);

    }

    // Lid screw bosses rise to the lid plane.
    for (x=[fastener_inset,case_length-fastener_inset])
        for (y=[fastener_inset,case_depth-fastener_inset])
            difference() {
                translate([x,y,case_height-boss_height]) cylinder(h=boss_height,d=boss_diameter);
                translate([x,y,case_height-boss_height-0.1])
                    cylinder(h=boss_height+0.2,d=lid_screw_diameter);
            }

    // Exterior dowel sleeves have a solid roof, keeping the enclosure floor closed.
    for (x=[case_length/2-dowel_socket_spacing/2,case_length/2+dowel_socket_spacing/2])
        translate([x,case_depth/2,0])
            difference() {
                translate([0,0,-dowel_socket_height])
                    cylinder(h=dowel_socket_height,d=dowel_diameter+dowel_socket_clearance+2*wall);
                translate([0,0,-dowel_socket_height-0.1])
                    cylinder(h=dowel_socket_height-dowel_socket_roof-dowel_socket_taper+0.1,
                             d=dowel_diameter+dowel_socket_clearance);
                translate([0,0,-dowel_socket_roof-dowel_socket_taper])
                    cylinder(h=dowel_socket_taper+0.1,
                             d1=dowel_diameter+dowel_socket_clearance,d2=1.0);
            }

}

module lid_assembled() {
    difference() {
        translate([0,0,case_height])
            rounded_box([case_length,case_depth,lid_thickness],corner_radius);
        for (x=[fastener_inset,case_length-fastener_inset])
            for (y=[fastener_inset,case_depth-fastener_inset])
                translate([x,y,case_height-0.1]) cylinder(h=lid_thickness+0.2,d=lid_screw_diameter);
    }
}

module lid_print() {
    // Flat service lid, printed with its underside on the build plate.
    difference() {
        rounded_box([case_length,case_depth,lid_thickness],corner_radius);
        for (x=[fastener_inset,case_length-fastener_inset])
            for (y=[fastener_inset,case_depth-fastener_inset])
                translate([x,y,-0.1]) cylinder(h=lid_thickness+0.2,d=lid_screw_diameter);
    }
}

if (part == "body") shell_body();
if (part == "lid") lid_print();
if (part == "assembly") { shell_body(); lid_assembled(); }
