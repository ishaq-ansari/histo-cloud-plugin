# Girder Integration in SegmentWSI

## Overview
The SegmentWSI CLI tool has been enhanced to automatically upload segmentation results to a Girder/DSA instance after inference completes. This implementation follows the pattern used in `sample.py`.

## Changes Made

### 1. SegmentWSI.py
- **Added import**: `girder_client` for Girder API interaction
- **Enhanced execution**: Capture exit code from vis.py to detect failures
- **Added upload logic**: Automatically uploads annotations to Girder if credentials are provided

### 2. SegmentWSI.xml
- **Added parameters section**: "Girder Upload" with three optional parameters:
  - `girderApiUrl`: Base URL of the Girder API
  - `girderToken`: Authentication token for API access
  - `girderItemId`: Target item ID (optional, can be auto-resolved)

## Usage

### Local-only execution (no Girder upload)
```bash
python SegmentWSI.py \
  --inputImageFile /path/to/image.svs \
  --inputModelFile /path/to/model.zip \
  --outputAnnotationFile /path/to/output.json
```

### With Girder upload
```bash
python SegmentWSI.py \
  --inputImageFile /path/to/image.svs \
  --inputModelFile /path/to/model.zip \
  --outputAnnotationFile /path/to/output.json \
  --girderApiUrl http://localhost:8080/api/v1 \
  --girderToken YOUR_API_TOKEN \
  --girderItemId ITEM_ID_HERE
```

## Implementation Details

### Connection and Authentication
```python
gc = girder_client.GirderClient(apiUrl=args.girderApiUrl)
gc.setToken(args.girderToken)
```

### Upload Process
1. **Run inference**: Execute vis.py to generate annotations
2. **Check exit code**: Ensure vis.py completed successfully
3. **Connect to Girder**: Establish API connection with provided credentials
4. **Resolve item ID**: Use provided ID or attempt to resolve from input image
5. **Post annotation**: Upload annotation data to Girder's annotation endpoint
6. **Upload file**: Upload the JSON file to the item for archival

### Error Handling
- Validates vis.py execution (exit code check)
- Checks for output file existence
- Graceful fallback if Girder credentials not provided
- Detailed error messages with stack traces
- Continues if item ID resolution fails (with warning)

### Backward Compatibility
- Girder upload is **optional**
- If no Girder credentials provided, behaves like original version
- All existing parameters and functionality preserved

## Girder API Endpoints Used

1. **POST /annotation**: Creates a new annotation on an item
   - Parameters: `itemId`
   - Body: Full annotation JSON payload
   - Returns: Annotation document with `_id`

2. **uploadFileToItem**: Uploads file as an attachment to an item
   - Parameters: item ID, file path, filename, MIME type
   - Returns: File document with metadata

## Testing

### Test 1: Local execution (no upload)
```bash
# Should work exactly as before, saving JSON locally only
python SegmentWSI.py --inputImageFile test.svs --inputModelFile model.zip --outputAnnotationFile output.json
```

### Test 2: Girder upload with explicit item ID
```bash
# Should upload both annotation and file to Girder
python SegmentWSI.py \
  --inputImageFile test.svs \
  --inputModelFile model.zip \
  --outputAnnotationFile output.json \
  --girderApiUrl http://dsa.server.com/api/v1 \
  --girderToken abcd1234... \
  --girderItemId 5f8e9d0a1c2b3a4567890abc
```

### Test 3: Check Girder UI
After successful upload, verify in DSA interface:
- Annotation layer should appear on the image viewer
- JSON file should be listed in item's file attachments

## Integration with Docker/HistomicsTK

When deployed as a HistomicsTK/DSA plugin:
1. DSA automatically provides `girderApiUrl` and `girderToken`
2. Input image reference is a Girder resource ID
3. Plugin automatically resolves item ID from input
4. Annotations appear immediately in DSA viewer after task completion

## Dependencies

Required Python packages:
- `girder_client`: Girder API client library (already in requirements)
- `json`: Standard library (built-in)

## Reference Implementation

This implementation is based on the pattern used in:
- `/home/iansari/test4_tf1/Histo-cloud/sample.py` (lines 350-411)

Key similarities:
- Same connection pattern with `GirderClient`
- Same authentication with `setToken`
- Same two-step upload process (annotation POST + file upload)
- Same error handling approach

## Future Enhancements

Potential improvements:
1. Support for item ID resolution from DSA resource URLs
2. Retry logic for network failures
3. Progress reporting for large file uploads
4. Support for updating existing annotations vs. creating new ones
5. Batch upload for multiple outputs
