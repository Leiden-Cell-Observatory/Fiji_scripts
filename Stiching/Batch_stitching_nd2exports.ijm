#@ File (label="Select input directory", style="directory") inputDir
#@ File (label="Select output directory", style="directory") outputDir
#@ String (label="Base filename (before well ID)", value="fiximaging before clearing_fiximaging before clearing") baseName
#@ Integer (label="Grid size X", value=3) gridX
#@ Integer (label="Grid size Y", value=3) gridY
#@ Integer (label="Tile overlap (%)", value=10) tileOverlap
#@ Integer (label="Number of channels", value=4) nChannels
#@ Integer (label="Number of Z-slices", value=11) numZSlices

/*
 * Grid Stitching and Hyperstack Conversion for Multi-Well Plates
 * 
 * This macro processes multi-well plate images that have been exported as individual tiles.
 * It performs grid stitching for each well and converts the result to a properly organized
 * hyperstack with channels and Z-slices.
 * 
 * Input requirements:
 * - Files named as: [basename]_[WellID]_[TileNumber].tif
 *   Example: fiximaging before clearing_fiximaging before clearing_A01_0000.tif
 * - Tiles numbered from 0000 to (gridX * gridY - 1)
 * - All tiles for a well should have the same dimensions
 * 
 * Processing steps:
 * 1. Scans input directory for all unique well IDs
 * 2. For each well: stitches tiles using Grid/Collection stitching
 * 3. Converts stitched stack to hyperstack (channels × Z-slices × timepoints)
 * 4. Saves result as [WellID].tif in output directory
 * 
 * Default configuration:
 * - 3×3 grid (9 tiles per well)
 * - Snake pattern (right & down)
 * - 4 channels, 11 Z-slices, 1 timepoint
 * - 10% tile overlap
 * 
 * Developed by Maarten Paul (m.w.paul@lacdr.leidenuniv.nl) @maartenpaul at Github
 * Version 2025-01-09: Initial version with flexible parameters
 */

setBatchMode(true);

// Get list of all files in input directory
fileList = getFileList(inputDir);

// Extract unique well IDs from filenames
wellIDs = newArray();
for (i = 0; i < fileList.length; i++) {
    if (endsWith(fileList[i], ".tif")) {
        // Extract well ID (e.g., A01, B02, etc.)
        filename = fileList[i];
        // Find the well ID pattern (letter + 2 digits)
        wellStart = indexOf(filename, "_", indexOf(filename, "_") + 1) + 1;
        wellEnd = indexOf(filename, "_", wellStart);
        wellID = substring(filename, wellStart, wellEnd);
        
        // Add to array if not already present
        if (!arrayContains(wellIDs, wellID)) {
            wellIDs = Array.concat(wellIDs, wellID);
        }
    }
}

// Sort well IDs alphabetically
Array.sort(wellIDs);

// Process each well
for (w = 0; w < wellIDs.length; w++) {
    wellID = wellIDs[w];
    
    // Construct file pattern for stitching
    filePattern = baseName + "_" + wellID + "_{iiii}.tif";
    
    // Run Grid/Collection stitching with snake pattern
    run("Grid/Collection stitching", 
        "type=[Grid: snake by rows] " +
        "order=[Right & Down                ] " +
        "grid_size_x=" + gridX + " " +
        "grid_size_y=" + gridY + " " +
        "tile_overlap=" + tileOverlap + " " +
        "first_file_index_i=0 " +
        "directory=[" + inputDir + "] " +
        "file_names=[" + filePattern + "] " +
        "output_textfile_name=TileConfiguration.txt " +
        "fusion_method=[Linear Blending] " +
        "regression_threshold=0.30 " +
        "max/avg_displacement_threshold=2.50 " +
        "absolute_displacement_threshold=3.50 " +
        "compute_overlap " +
        "computation_parameters=[Save computation time (but use more RAM)] " +
        "image_output=[Fuse and display]");
    
    // Convert stitched stack to hyperstack (XYCZT ordering)
    run("Stack to Hyperstack...", 
        "order=xyczt(default) " +
        "channels=" + nChannels + " " +
        "slices=" + numZSlices + " " +
        "frames=1 " +
        "display=Color");
    
    // Save the result
    outputPath = outputDir + File.separator + wellID + ".tif";
    saveAs("Tiff", outputPath);
    close();
}

setBatchMode(false);

// Helper function to check if array contains value
function arrayContains(array, value) {
    for (i = 0; i < array.length; i++) {
        if (array[i] == value) {
            return true;
        }
    }
    return false;
}
