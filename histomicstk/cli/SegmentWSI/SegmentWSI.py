import os, zipfile, json
from histomicstk.cli.utils import CLIArgumentParser
from glob import glob
import sys
import girder_client

def main(args):

    # Setup Girder client and download input image
    gc = girder_client.GirderClient(apiUrl=args.girderApiUrl)
    gc.setToken(args.girderToken)

    # Get file info from Girder
    file_id = args.inputImageFile
    file_info = gc.get(f"/file/{file_id}")
    item_id = file_info["itemId"]
    file_name = file_info["name"]
    print(f"Running on: {file_name}")

    # Determine working directory
    try:
        if os.path.isdir("/mnt/girder_worker") and len(os.listdir("/mnt/girder_worker")) > 0:
            mounted_path = os.path.join("/mnt/girder_worker", os.listdir("/mnt/girder_worker")[0])
        else:
            raise FileNotFoundError
    except Exception:
        local_tmp = os.path.join(os.getcwd(), "tmp_girder_worker", "worker")
        os.makedirs(local_tmp, exist_ok=True)
        mounted_path = local_tmp

    # Download the image file
    input_image_path = os.path.join(mounted_path, file_name)
    os.makedirs(os.path.dirname(input_image_path), exist_ok=True)
    gc.downloadFile(file_id, input_image_path)
    print(f"Downloaded image to: {input_image_path}")

    def get_base_model_name(model_file):
        try:
            base_model = model_file.split('.meta')
            assert len(base_model) == 2
            base_model = base_model[0]
        except:
            try:
                base_model = model_file.split('.index')
                assert len(base_model) == 2
                base_model = base_model[0]
            except:
                try:
                    base_model = model_file.split('.data')
                    assert len(base_model) == 2
                    base_model = base_model[0]
                except:
                    base_model = model_file
        return base_model

    cwd = os.getcwd()
    print(cwd)

    # Use mounted_path as working directory for model extraction
    tmp = mounted_path
    print("Working directory: {}".format(tmp))

    # move to data folder and extract models
    os.chdir(tmp)
    # unpck model files from zipped folder
    with open(args.inputModelFile, 'rb') as fh:
        z = zipfile.ZipFile(fh)
        for name in z.namelist():
            z.extract(name, tmp)
    # get num_classes from json file
    with open('args.txt', 'rb') as file:
        trainingDict = json.load(file)
    num_classes = trainingDict['num_classes']
    compartments = trainingDict['compartments']

    # move back to cli folder
    os.chdir(cwd)

    model_files = glob('{}/*.ckpt*'.format(tmp))
    print(model_files)
    model_file = model_files[0]
    model = get_base_model_name(model_file)

    # list files code can see
    os.system('ls -l {}'.format(model.split('model.ckpt')[0]))

    # Output annotation file path
    output_annotation_file = os.path.join(tmp, "annotation.json")
    print('\noutput filename: {}\n'.format(output_annotation_file))

    # run vis.py with flags
    cmd = "python3 ../deeplab/vis.py --model_variant xception_65 --atrous_rates 6 --atrous_rates 12 --atrous_rates 18 --output_stride 16 --decoder_output_stride 4 --save_json_annotation True --checkpoint_dir {} --dataset_dir '{}' --json_filename '{}' --vis_crop_size {} --wsi_downsample {} --tile_step {} --min_size {} --vis_batch_size {} --vis_remove_border {} --simplify_contours {} --num_classes {} --class_names '{}' --save_heatmap={} --heatmap_stride {} --gpu {}".format(model, input_image_path, output_annotation_file, args.patch_size, args.wsi_downsample, args.tile_stride, args.min_size, args.batch_size, args.remove_border, args.simplify_contours, num_classes, compartments, args.save_heatmap, args.heatmap_stride, args.gpu)
    print(cmd)
    sys.stdout.flush()
    os.system(cmd)

    # Verify the output file was created and upload to Girder
    if os.path.exists(output_annotation_file):
        print("\nAnnotation file successfully created: {}".format(output_annotation_file))
        file_size = os.path.getsize(output_annotation_file)
        print("File size: {} bytes".format(file_size))
        
        # Upload annotation to Girder
        try:
            with open(output_annotation_file, 'r') as f:
                annotation_data = json.load(f)
            
            # Post annotation to the item
            gc.post(f'/annotation/item/{item_id}', json=annotation_data)
            print(f"Successfully uploaded annotation to Girder item {item_id}")
        except Exception as e:
            print(f"Error uploading annotation to Girder: {e}")
            sys.exit(1)
    else:
        print("ERROR: Output annotation file was not created: {}".format(output_annotation_file))
        sys.exit(1)
    
    print("\nSegmentation complete.")

if __name__ == "__main__":
    main(CLIArgumentParser().parse_args())