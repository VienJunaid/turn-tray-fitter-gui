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
    if not os.path.isfile(json_path):
        return False
    return True

# --- HORIZONTAL PACKING: CYLINDERS ---

def pack_circles_in_circle(R_eff, r_eff): 
    count = 0

    if r_eff <= R_eff:
        count += 1

    k = 1
    while True:
        r_k = 2 * k * r_eff 
        if r_k + r_eff > R_eff:
            break 
        count += math.floor((2 * math.pi * r_k) / (2 * r_eff))
        k += 1
    return count



# --- HORIZONTAL PACKING: CUBES & RECT PRISMS ---

def pack_rects_in_circle(R_eff, l_eff, w_eff):
    best_count = 0

    for ox, oy in [(0, 0), (l_eff / 2, w_eff / 2)]:
        count = 0
        x = -R_eff + ox
        while x <= R_eff:
            y = -R_eff + oy
            while y <= R_eff:
                corners = [
                    (x - l_eff / 2, y - w_eff / 2),
                    (x + l_eff / 2, y - w_eff / 2),
                    (x - l_eff / 2, y + w_eff / 2),
                    (x + l_eff / 2, y + w_eff / 2),
                ]
                if all(math.sqrt(cx**2 + cy**2) <= R_eff for cx, cy in corners):
                    count += 1
                y += w_eff
            x += l_eff
        best_count = max(best_count, count)

    return best_count


# --- SAFETY MARGIN ---

def apply_horizontal_safety_margin(count):
    return max(0, count - 1) 


# --- VERTICAL STACKING ---

def layers_available(H_usable, h_eff):
    return math.floor(H_usable / h_eff) 


# --- SHAPE NORMALIZATION ---

def normalize_to_footprint(shape, dims):
    if shape == "C":
        r, h = dims
        return ("circle", r + GAP / 2, h + GAP)
    elif shape == "S":
        s = dims[0]
        return ("rectangle", (s + GAP, s + GAP), s + GAP)
    elif shape == "R":
        l, w, h = dims
        return ("rectangle", (l + GAP, w + GAP), h + GAP)


# --- ALLOCATION ---

def allocate_single_type(freezer, shape, dims):
    R_eff = freezer["R"] - GAP
    H_usable = freezer["H"] - freezer["handle_bar_clearance"]

    footprint_type, footprint_dims_eff, h_eff = normalize_to_footprint(shape, dims)

    if footprint_type == "circle":
        raw_count = pack_circles_in_circle(R_eff, footprint_dims_eff)
    else:
        l_eff, w_eff = footprint_dims_eff
        raw_count = pack_rects_in_circle(R_eff, l_eff, w_eff)

    objects_per_layer = apply_horizontal_safety_margin(raw_count)
    num_layers = layers_available(H_usable, h_eff)
    total_fit = objects_per_layer * num_layers

    return { "total_capacity": total_fit } 

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
    try:
        freezer = load_freezer(model_id, json_path)
    except KeyError as e:
        print(e) 
        return

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
            length = input("Length of Rectangle: ")
            width = input ("Width of Rectangle: ")
            height = input("Height of Rectangle: ")
            dimensions = (float(length), float(width), float(height)) 
        case _:
            print("Must be either: C, S, or R") 
            return 

    result = allocate_single_type(freezer, user_shape, dimensions)
    print(f"Total freezer capacity for this object: {result['total_capacity']}")

if __name__ == "__main__":
    main() 
