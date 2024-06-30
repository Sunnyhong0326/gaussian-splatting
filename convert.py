#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import os
import logging
from argparse import ArgumentParser
import shutil
import time

# This Python script is based on the shell converter script provided in the MipNerF 360 repository.
parser = ArgumentParser("Colmap converter")
parser.add_argument("--no_gpu", action='store_true')
parser.add_argument("--skip_matching", action='store_true')
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--camera", default="OPENCV", type=str)
parser.add_argument("--colmap_executable", default="", type=str)
parser.add_argument("--resize", action="store_true")
parser.add_argument("--magick_executable", default="", type=str)
parser.add_argument("--img_path", "-img", required=False, default=None, type=str)
parser.add_argument("--sequential_matcher", "-seq_matcher", action="store_true")
args = parser.parse_args()
colmap_command = '"{}"'.format(args.colmap_executable) if len(args.colmap_executable) > 0 else "colmap"
magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
use_gpu = 1 if not args.no_gpu else 0

log_path = os.path.join(args.source_path,'log.txt')
log_info = []

# Parse input image folder
if args.img_path is not None:
    img_path = args.img_path
else:
    img_path = os.path.join(args.source_path, "input")

if not os.path.exists(img_path):
    logging.error(f"Image folder: {img_path} does not exists!")
    exit(0)
log_info.append(f"Images folder: {img_path}\n")

matcher = 'sequential_matcher' if args.sequential_matcher else 'exhaustive_matcher'
log_info.append(f'Matcher: {matcher}\n')

# Record the starting time
start_time = time.time()
if not args.skip_matching:
    os.makedirs(args.source_path + "/distorted/sparse", exist_ok=True)

    ## Feature extraction
    feat_extracton_cmd = colmap_command + " feature_extractor "\
        "--database_path " + args.source_path + "/distorted/database.db \
        --image_path " + img_path + " \
        --ImageReader.single_camera 1 \
        --ImageReader.camera_model " + args.camera + " \
        --SiftExtraction.use_gpu " + str(use_gpu)
    exit_code = os.system(feat_extracton_cmd)
    if exit_code != 0:
        logging.error(f"Feature extraction failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ## Feature matching
    feat_matching_cmd = colmap_command + f" {matcher} \
        --database_path " + args.source_path + "/distorted/database.db \
        --SiftMatching.use_gpu " + str(use_gpu)
    exit_code = os.system(feat_matching_cmd)
    if exit_code != 0:
        logging.error(f"Feature matching failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ### Bundle adjustment
    # The default Mapper tolerance is unnecessarily large,
    # decreasing it speeds up bundle adjustment steps.
    mapper_cmd = (colmap_command + " mapper \
        --database_path " + args.source_path + "/distorted/database.db \
        --image_path "  + img_path + " \
        --output_path "  + args.source_path + "/distorted/sparse \
        --Mapper.ba_global_function_tolerance=0.000001")
    exit_code = os.system(mapper_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        exit(exit_code)

# Perform manhattan world alignment
# aligner_cmd = (colmap_command + " model_orientation_aligner \
#     --image_path " + img_path + " \
#     --input_path " + args.source_path + "/distorted/sparse/0 \
#     --output_path " + args.source_path + "/distorted/sparse/0")
# exit_code = os.system(aligner_cmd)
# if exit_code != 0:
#     logging.error(f"Aligner failed with code {exit_code}. Exiting.")
#     exit(exit_code)

### Model alignment
# Aligns the scene so that +Z axis is up. 
model_alignment_cmd = (colmap_command + " model_aligner \
    --input_path " + args.source_path + "/distorted/sparse/0 \
    --database_path " + args.source_path + "/distorted/database.db \
    --robust_alignment_max_error  " + "0.1" "\
    --alignment_type  " + "plane" "\
    --output_path " + args.source_path + "/distorted/sparse/0")
print(model_alignment_cmd)
exit_code = os.system(model_alignment_cmd)
if exit_code != 0:
    logging.error(f"Model aligner failed with code {exit_code}. Exiting.")
    exit(exit_code)

### Image undistortion
## We need to undistort our images into ideal pinhole intrinsics.
# Note: output_path automatically produce images, sparse and stereo folder
############################################################################
img_undist_cmd = (colmap_command + " image_undistorter \
    --image_path " + img_path + " \
    --input_path " + args.source_path + "/distorted/sparse/0 \
    --output_path " + args.source_path + "\
    --output_type COLMAP")
exit_code = os.system(img_undist_cmd)
if exit_code != 0:
    logging.error(f"Mapper failed with code {exit_code}. Exiting.")
    exit(exit_code)

files = os.listdir(args.source_path + "/sparse")
os.makedirs(args.source_path + "/sparse/0", exist_ok=True)
# Copy each file from the source directory to the destination directory
for file in files:
    if file == '0':
        continue
    source_file = os.path.join(args.source_path, "sparse", file)
    destination_file = os.path.join(args.source_path, "sparse", "0", file)
    shutil.move(source_file, destination_file)

# Record the ending time
end_time = time.time()
# Calculate the elapsed time
elapsed_time = end_time - start_time
time_in_second = f"Elapsed Time: {elapsed_time} seconds\n"
time_in_minute = f"Elapsed Time: {int(elapsed_time/60)} minutes {elapsed_time%60} seconds\n"
log_info.append(time_in_second)
log_info.append(time_in_minute)

with open(log_path, 'w') as file:
    file.write(''.join(log_info))

if(args.resize):
    print("Copying and resizing...")

    # Resize images.
    os.makedirs(args.source_path + "/images_2", exist_ok=True)
    os.makedirs(args.source_path + "/images_4", exist_ok=True)
    os.makedirs(args.source_path + "/images_8", exist_ok=True)
    # Get the list of files in the source directory
    files = os.listdir(args.source_path + "/images")
    # Copy each file from the source directory to the destination directory
    for file in files:
        source_file = os.path.join(args.source_path, "images", file)

        destination_file = os.path.join(args.source_path, "images_2", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 50% " + destination_file)
        if exit_code != 0:
            logging.error(f"50% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

        destination_file = os.path.join(args.source_path, "images_4", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 25% " + destination_file)
        if exit_code != 0:
            logging.error(f"25% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

        destination_file = os.path.join(args.source_path, "images_8", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 12.5% " + destination_file)
        if exit_code != 0:
            logging.error(f"12.5% resize failed with code {exit_code}. Exiting.")
            exit(exit_code)

print("Done.")
