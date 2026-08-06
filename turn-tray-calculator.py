# Python Script for the Turn Tray Fitter GUI 

# Structure
# JSON File containing all Model ID, Dimensions(L*W*H)
#
#
# Python Script
# 1. Read the Model ID in the command line 
# 2. Check if this model exists first
# 3. If model exists, then ask for dimensions and shape of object USER is trying to insert into freezer
# 4. Calculate area and volume of the freezer
# 5. Calculate how many "objects" can fit inside the freezer (horizontal and vertical layer) 
# 6. Output results (fit count)

import math 
import json
import os 

directory = '' # Location of JSON files 

GAP = 3.175 # everything is in milimeters mm 

def load_freezer(model_id, json_path): 
    with open(json_path, 'r') as file:
        data = json.load(file) 
    
    for model in data["models"]:
        if model["model_id"] == model_id:
            return model
    raise KeyError("Freezer Model is not found in database.")


def json_checker(json_path):
    # TODO: current logic checks if a string is "in" the directory string — that's wrong, fix it
    # TODO: return True/False or raise FileNotFoundError so main() can decide what to do
    if not os.path.isfile(json_path):
        return False
    return True

# --- HORIZONTAL PACKING: CYLINDERS ---

def pack_circles_in_circle(R_eff, r_eff):
    # Pack cylinder objects (circles) into the freezer cross-section (circle of radius R_eff)
    # Uses ring-based placement:
    #   Ring 0 (center): place 1 object if r_eff <= R_eff
    #   Ring k: place objects at radius r_k from center
    #     r_k = 2 * k * r_eff  (each ring is one diameter further out)
    #     count_k = floor( (2 * pi * r_k) / (2 * r_eff) )
    #     stop adding rings when r_k + r_eff > R_eff (object would poke past the wall)
    # TODO: implement ring 0 check
    # TODO: implement ring loop (k = 1, 2, ... until ring no longer fits)
    # TODO: sum all ring counts and return total
    # NOTE: r_eff already has GAP/2 baked in — do NOT add gap again inside this function
    pass


# --- HORIZONTAL PACKING: CUBES & RECT PRISMS ---

def pack_rects_in_circle(R_eff, l_eff, w_eff):
    # Pack rectangular footprints (grid of l_eff x w_eff cells) into the freezer circle
    # Uses grid-scan with multiple offsets to maximize fit:
    #   - Try a grid centered at (0,0) AND a grid shifted by (l_eff/2, w_eff/2)
    #   - For each candidate cell center (cx, cy), check all FOUR corners of the rectangle:
    #       corners: (cx ± l_eff/2, cy ± w_eff/2)
    #       valid only if ALL four corners satisfy sqrt(x^2 + y^2) <= R_eff
    #   - Count valid cells for each offset, keep the max
    # TODO: implement the offset loop (at minimum try origin-centered and half-cell-shifted)
    # TODO: implement the four-corner check for each candidate cell
    # TODO: return the best (highest) valid count across all offsets
    # NOTE: for cubes, caller passes l_eff = w_eff = s + GAP — no special case needed here
    pass


# --- SAFETY MARGIN ---

def apply_horizontal_safety_margin(count):
    # Mandatory "-1" rule on top of normal floor truncation (spec section 3c)
    # This is NOT a math floor — it's a deliberate real-world buffer for imperfectplacement
    # TODO: return max(0, count - 1)
    pass


# --- VERTICAL STACKING ---

def layers_available(H_usable, h_eff):
    # H_usable = H - handle_bar_clearance  (computed in main/allocate, not here)
    # h_eff    = object_height + GAP
    # TODO: return floor(H_usable / h_eff)
    # NOTE: no extra "-1" applied here — the handle_bar_clearance IS the vertical safety buffer
    #       (open question #2 in spec: confirm no additional vertical margin is needed)
    pass


# --- SHAPE NORMALIZATION ---

def normalize_to_footprint(shape, dims):
    # Converts raw user dimensions into effective packing dims (GAP already baked in)
    # Returns: (footprint_type, footprint_dims_eff, h_eff)
    #   shape == "C" (cylinder):   dims = (r, h)
    #     -> ("circle",    r + GAP/2,                      h + GAP)
    #   shape == "S" (cube/square): dims = (s,)
    #     -> ("rectangle", (s + GAP, s + GAP),              s + GAP)
    #   shape == "R" (rect prism): dims = (l, w, h)
    #     -> ("rectangle", (l + GAP, w + GAP),              h + GAP)
    #       OPEN QUESTION #1: rect prism orientation — default smallest dim as height?
    #       spec says to confirm this before implementing; flag it here
    # TODO: implement each branch and return the triple
    pass


# --- ALLOCATION ---

def allocate_single_type(freezer, shape, dims):
    # Ties everything together for one object type:
    # 1. Compute R_eff = freezer["R"] - GAP
    # 2. Compute H_usable = freezer["H"] - freezer["handle_bar_clearance"]
    # 3. Call normalize_to_footprint to get footprint_type, footprint_dims_eff, h_eff
    # 4. Call pack_circles_in_circle OR pack_rects_in_circle depending on footprint_type
    # 5. Call apply_horizontal_safety_margin on the raw count
    # 6. Call layers_available(H_usable, h_eff)
    # 7. total_fit = objects_per_layer_final * num_layers
    # TODO: implement all steps above
    pass


# FUTURE (not v1): allocate_multi_type for mixed shapes in one freezer
# def allocate_multi_type(freezer, object_list):
#   - open question #3: whole-layer-per-type (v1 default) vs mixed-type-per-layer
#   - for v1: loop over each type, call allocate_single_type, sum totals
#   pass

def main():
    # Enter the Model ID in the command line 
    model_id = input("Enter the Freezer Model ID: ")

    # Call a checker function to check if this exists 
    json_path = os.path.join(directory, "freezer_models.json")
    
    if not json_checker(json_path):
        print("JSON file containing all the freezer models is missing.")
        return

    # Loading Freezer to get Freezer dict 
    # TODO: handle cases where model_id is not found 
    freezer = load_freezer(model_id, json_path)
    
    # ask for the shape the user is trying to insert into freezer 
    user_shape = input("What shape are you trying to put into the freezer?: (C: Cylinder, S: Square (cube), R: Rectangle) ")
    
    match user_shape:
        case "C":
            radius = input("Radius of Cylinder: ")
            height = input("Height of Cylinder: ")
            dimensions = (float(radius), float(height))
        case "S":
            sides = input("Give us the length of the square: ")
            dimensions = (float(sides),)
        case "R":
            length = input("Lenght of Rectangle: ")
            width = input ("Width of Rectangle: ")
            height = input("Height of Rectangle: ")
            dimensions = (float(length), float(width), float(height)) 
        case _:
            print("Must be either: C, S, or R") 
            return 

    result = allocate_single_type(freezer, user_shape, dimensions) 
    print(f"Objects that fit: {result['fit']}")
    print(f"Leftover (won't fit): {result['leftover']}")
    print(f"Total freezer capacity for this object: {result['total_capacity']}")

if __name__ == "__main__":
    main() 
