#@ File[] (label="Select input files", style="files") input_files
#@ Integer (label="Channel to segment", value=1, min=1) target_channel
#@ Double (label="Probability threshold", value=0.5, min=0, max=1, stepSize=0.1) prob_threshold
#@ Double (label="Overlap threshold", value=0.3, min=0, max=1, stepSize=0.1) overlap_threshold
#@ Double (label="Min IOU for z-connection", value=0.1, min=0, max=1, stepSize=0.05) min_iou
#@ Boolean (label="Append labels to original image", value=true) append_to_original
#@ File (label="Output directory", style="directory") output_dir

# Script to create semi-3D stardist segmentation from 3D-timeseries using TrackMate
# As explained here: https://imagej.net/plugins/trackmate/detectors/trackmate-stardist
# Developed by Maarten Paul (m.w.paul@lacdr.leidenuniv.nl) @maartenpaul at Github

# Version 2025-11-21: Initial version of the script

import sys
import os
from ij import IJ, ImagePlus, ImageStack
from ij.plugin import Duplicator, HyperStackConverter, RGBStackMerge
from fiji.plugin.trackmate import Model, Settings, TrackMate, Logger
from fiji.plugin.trackmate.stardist import StarDistDetectorFactory
from fiji.plugin.trackmate.tracking.overlap import OverlapTrackerFactory
from fiji.plugin.trackmate.action.LabelImgExporter import LabelIdPainting
import fiji.plugin.trackmate.action.LabelImgExporter as LabelImgExporter
from java.io import File

# Set UTF-8 encoding
reload(sys)
sys.setdefaultencoding('utf-8')

print("=" * 60)
print("3D NUCLEI SEGMENTATION WITH STARDIST")
print("=" * 60)
print("Number of files to process: {}".format(len(input_files)))
print("Append to original: {}".format(append_to_original))
print("=" * 60)

# Process each file
for file_idx, input_file in enumerate(input_files):
    print("\n" + "=" * 60)
    print("FILE {} / {}: {}".format(file_idx + 1, len(input_files), input_file.getName()))
    print("=" * 60)
    
    try:
        # Open the image (handles nd2, tif, etc.)
        print("Opening image...")
        imp = IJ.openImage(input_file.getAbsolutePath())
        if imp is None:
            print("ERROR: Could not open file")
            continue
        
        # Get image dimensions
        width = imp.getWidth()
        height = imp.getHeight()
        n_channels = imp.getNChannels()
        n_slices = imp.getNSlices()
        n_frames = imp.getNFrames()
        
        print("Image dimensions: {} x {}".format(width, height))
        print("Channels: {}, Z-slices: {}, Timepoints: {}".format(n_channels, n_slices, n_frames))
        
        # Validate inputs
        if target_channel < 1 or target_channel > n_channels:
            print("ERROR: Channel {} is out of range (image has {} channels)".format(
                target_channel, n_channels))
            imp.close()
            continue
        
        if n_slices < 2:
            print("WARNING: Image has only {} z-slice(s)".format(n_slices))
        
        # Create output stack for labels
        output_stack = ImageStack(width, height)
        successful_timepoints = 0
        
        # Process each timepoint
        for t in range(1, n_frames + 1):
            print("\nProcessing timepoint {} / {}...".format(t, n_frames))
            
            try:
                # Extract single timepoint with all z-slices
                imp_t = Duplicator().run(imp, target_channel, target_channel, 1, n_slices, t, t)
                
                # Convert Z-slices to frames for TrackMate
                imp_t.setDimensions(1, 1, n_slices)
                
                # Set up TrackMate
                model = Model()
                model.setLogger(Logger.IJ_LOGGER)
                
                settings = Settings(imp_t)
                
                # StarDist detector
                settings.detectorFactory = StarDistDetectorFactory()
                settings.detectorSettings = {
                    'TARGET_CHANNEL': 1,
                    'SCORE_THRESHOLD': prob_threshold,
                    'OVERLAP_THRESHOLD': overlap_threshold
                }
                
                # Overlap tracker
                settings.trackerFactory = OverlapTrackerFactory()
                settings.trackerSettings = {
                    'IOU_CALCULATION': 'PRECISE',
                    'MIN_IOU': min_iou,
                    'SCALE_FACTOR': 1.0
                }
                
                settings.addAllAnalyzers()
                
                # Run TrackMate
                trackmate = TrackMate(model, settings)
                
                if not trackmate.checkInput():
                    print("  ERROR: {}".format(trackmate.getErrorMessage()))
                    imp_t.close()
                    # Add empty slices
                    for z in range(n_slices):
                        empty_ip = IJ.createImage("Empty", width, height, 1, 16).getProcessor()
                        output_stack.addSlice("t{}_z{}_empty".format(t, z+1), empty_ip)
                    continue
                
                if not trackmate.process():
                    print("  ERROR: {}".format(trackmate.getErrorMessage()))
                    imp_t.close()
                    # Add empty slices
                    for z in range(n_slices):
                        empty_ip = IJ.createImage("Empty", width, height, 1, 16).getProcessor()
                        output_stack.addSlice("t{}_z{}_empty".format(t, z+1), empty_ip)
                    continue
                
                n_spots = model.getSpots().getNSpots(False)
                n_tracks = model.getTrackModel().nTracks(False)
                print("  Found {} spots in {} 3D nuclei".format(n_spots, n_tracks))
                
                # Create label image
                label_imp_t = LabelImgExporter.createLabelImagePlus(
                    trackmate,
                    False,
                    True,
                    LabelIdPainting.LABEL_IS_TRACK_ID
                )
                
                if label_imp_t is None:
                    print("  WARNING: Label image creation failed")
                    imp_t.close()
                    # Add empty slices
                    for z in range(n_slices):
                        empty_ip = IJ.createImage("Empty", width, height, 1, 16).getProcessor()
                        output_stack.addSlice("t{}_z{}_empty".format(t, z+1), empty_ip)
                    continue
                
                # Convert frames back to z-slices
                n_label_frames = label_imp_t.getNFrames()
                label_imp_t.setDimensions(1, n_label_frames, 1)
                
                # Add to output stack
                for z in range(1, label_imp_t.getNSlices() + 1):
                    label_imp_t.setSlice(z)
                    ip = label_imp_t.getProcessor().duplicate()
                    output_stack.addSlice("t{}_z{}".format(t, z), ip)
                
                successful_timepoints += 1
                
                # Clean up
                label_imp_t.close()
                imp_t.close()
                
            except Exception as e:
                print("  ERROR: {}".format(str(e)))
                # Add empty slices
                for z in range(n_slices):
                    empty_ip = IJ.createImage("Empty", width, height, 1, 16).getProcessor()
                    output_stack.addSlice("t{}_z{}_error".format(t, z+1), empty_ip)
        
        print("\nSuccessfully processed {} / {} timepoints".format(successful_timepoints, n_frames))
        
        if output_stack.getSize() == 0:
            print("ERROR: No labels created")
            imp.close()
            continue
        
        # Create label hyperstack
        print("Creating label hyperstack...")
        label_imp = ImagePlus("Labels", output_stack)
        label_imp = HyperStackConverter.toHyperStack(
            label_imp, 
            1,
            n_slices,
            n_frames,
            "default",
            "Grayscale"
        )
        
        # Set calibration
        cal = imp.getCalibration()
        label_imp.setCalibration(cal)
        
        # Prepare output filename (always .tif)
        original_name = input_file.getName()
        # Remove extension regardless of input format
        name_without_ext = os.path.splitext(original_name)[0]
        
        if append_to_original:
            print("Appending labels to original image...")
            
            # Check if original is already multi-channel
            if n_channels == 1:
                # Original is single channel, merge with labels
                merged_imp = RGBStackMerge.mergeChannels([imp, label_imp], False)
                merged_imp.setTitle(name_without_ext + "_with_labels")
                
                # Set calibration
                merged_imp.setCalibration(cal)
                
                # Save merged image as TIFF
                output_file = File(output_dir, name_without_ext + "_with_labels.tif")
                IJ.save(merged_imp, output_file.getAbsolutePath())
                print("Saved merged image: {}".format(output_file.getName()))
                
                merged_imp.close()
            else:
                # Original has multiple channels, need to add label as new channel
                print("  Creating stack with {} original channels + 1 label channel...".format(n_channels))
                
                # Create list of channels: all original channels + label channel
                channels = []
                for c in range(1, n_channels + 1):
                    ch_imp = Duplicator().run(imp, c, c, 1, n_slices, 1, n_frames)
                    channels.append(ch_imp)
                channels.append(label_imp)
                
                # Merge all channels
                merged_imp = RGBStackMerge.mergeChannels(channels, False)
                merged_imp.setTitle(name_without_ext + "_with_labels")
                
                # Set calibration
                merged_imp.setCalibration(cal)
                
                # Save merged image as TIFF
                output_file = File(output_dir, name_without_ext + "_with_labels.tif")
                IJ.save(merged_imp, output_file.getAbsolutePath())
                print("Saved merged image: {}".format(output_file.getName()))
                
                # Close channel images
                for ch_imp in channels[:-1]:  # Don't close label_imp, we'll close it below
                    ch_imp.close()
                merged_imp.close()
        else:
            # Save labels as separate TIFF file
            output_file = File(output_dir, name_without_ext + "_label_3D.tif")
            IJ.save(label_imp, output_file.getAbsolutePath())
            print("Saved label image: {}".format(output_file.getName()))
        
        # Clean up
        label_imp.close()
        imp.close()
        
        print("Completed processing: {}".format(original_name))
        
    except Exception as e:
        print("ERROR processing file: {}".format(str(e)))
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("ALL FILES PROCESSED")
print("=" * 60)
