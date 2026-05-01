// =========================================================================
// Batch stitching for multi-well, multi-channel grid acquisitions
//
// Expected filename structure:
//   <basename>_<well>_<tileIndex>_<channel>.tif
//   e.g. 11042026_FUCCI_..._65Wells_A01_0000_AF405.tif
//
// Output: one stitched TIFF per well/channel in subfolder "stitched/"
//   e.g. stitched/A01_AF405.tif
// =========================================================================

#@ File (label="Input directory", style="directory") inputDir
#@ String (label="Base name (everything before _<well>_)", value="11042026_FUCCI_24HExposure_PDLO_ChannelAF405,AF488,Cy3,TD_Seq0000_crop-MaxIP_65Wells") basename
#@ String (label="Channels (comma-separated)", value="AF405,AF488,Cy3,TD") channelsStr
#@ Integer (label="Grid size X", value=3) gridX
#@ Integer (label="Grid size Y", value=3) gridY
#@ Double (label="Tile overlap (%)", value=10) overlap

// Ensure the input path ends with a separator
inputPath = inputDir;
if (!endsWith(inputPath, "/") && !endsWith(inputPath, "\\")) {
    inputPath = inputPath + File.separator;
}

// Create the output subfolder for stitched results
outputDir = inputPath + "stitched" + File.separator;
File.makeDirectory(outputDir);

// Parse the channel list
channels = split(channelsStr, ",");

// Discover wells by scanning for tile-0000 files of the first channel
files = getFileList(inputPath);
endMarker = "_0000_" + channels[0] + ".tif";
wellsBuffer = newArray(1000);
wellCount = 0;

for (i = 0; i < files.length; i++) {
    if (endsWith(files[i], endMarker)) {
        // The well is the segment between the last underscore and "_0000_<channel>.tif"
        beforeMarker = substring(files[i], 0, lengthOf(files[i]) - lengthOf(endMarker));
        well = substring(beforeMarker, lastIndexOf(beforeMarker, "_") + 1);

        // Keep only unique well IDs
        isNew = true;
        for (k = 0; k < wellCount; k++) {
            if (wellsBuffer[k] == well) isNew = false;
        }
        if (isNew) {
            wellsBuffer[wellCount] = well;
            wellCount++;
        }
    }
}

wells = Array.trim(wellsBuffer, wellCount);
Array.sort(wells);

// Print a small summary to the Log
wellList = "";
for (i = 0; i < wells.length; i++) {
    if (i > 0) wellList = wellList + ", ";
    wellList = wellList + wells[i];
}
print("Found " + wells.length + " wells: " + wellList);
print("Channels: " + channelsStr);
print("Output: " + outputDir);
print("");

setBatchMode(true);

// Stitch every well x channel combination
for (w = 0; w < wells.length; w++) {
    well = wells[w];
    for (c = 0; c < channels.length; c++) {
        channel = channels[c];
        print("Stitching " + well + " / " + channel);

        // Filename pattern this run will look for
        filePattern = basename + "_" + well + "_{iiii}_" + channel + ".tif";

        // Unique TileConfig filename so different runs don't overwrite each other
        configName = "TileConfig_" + well + "_" + channel + ".txt";

        // Run the stitching plugin and have it produce a fused image
        run("Grid/Collection stitching",
            "type=[Grid: snake by rows]" +
            " order=[Right & Down                ]" +
            " grid_size_x=" + gridX +
            " grid_size_y=" + gridY +
            " tile_overlap=" + overlap +
            " first_file_index_i=0" +
            " directory=[" + inputPath + "]" +
            " file_names=[" + filePattern + "]" +
            " output_textfile_name=" + configName +
            " fusion_method=[Linear Blending]" +
            " regression_threshold=0.30" +
            " max/avg_displacement_threshold=2.50" +
            " absolute_displacement_threshold=3.50" +
            " compute_overlap" +
            " computation_parameters=[Save computation time (but use more RAM)]");

        // Save the fused image with a clean name and close it
        outputPath = outputDir + well + "_" + channel + ".tif";
        saveAs("Tiff", outputPath);
        close();
    }
}

setBatchMode(false);
print("");
print("Done.");