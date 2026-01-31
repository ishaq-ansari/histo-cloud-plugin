import os, sys, json, tempfile, re
import datetime
import warnings
import girder_client
import logging
from pathlib import Path
from ctk_cli import CLIArgumentParser

warnings.filterwarnings("ignore", category=UserWarning)
print("RUNNING:", __file__)
print("ARGV:", sys.argv)

WSI_EXTS = (".svs", ".tif", ".tiff", ".ndpi", ".scn", ".svslide")


def set_logger():
    log_path = os.path.join("/tmp", "process_log.log")
    logging.basicConfig(
        filename=log_path,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(console_handler)


def _pick_workdir():
    """
    Determine a suitable working directory for the pipeline.
    Preference order:
      1. If /mnt/girder_worker exists and contains a subdir, return that subdir (container behavior).
      2. Use TMPDIR/TEMP/TMP environment variables if set and valid.
      3. Fallback to tempfile.gettempdir().
    Returns an absolute directory path.
    """
    # 1) container-mounted girder worker (common on DSA/Girder worker)
    try:
        gw = "/mnt/girder_worker"
        if os.path.isdir(gw):
            entries = [e for e in os.listdir(gw) if not e.startswith(".")]
            if entries:
                # choose the first non-hidden entry (this matches previous behavior)
                return os.path.join(gw, entries[0])
            # if the folder exists but is empty, fall through to envs
    except Exception:
        pass

    # 2) use temp env vars if available
    for env in ("TMPDIR", "TEMP", "TMP"):
        p = os.getenv(env)
        if p and os.path.isdir(p):
            return p

    # 3) fallback
    return tempfile.gettempdir()


def _resolve_file_and_item(gc: girder_client.GirderClient, input_id: str):
    """
    Return (file_doc, item_doc). Accepts either a file _id or an item _id.
    If item id: choose the most suitable WSI file under the item.
    """
    # Try as file id
    try:
        fdoc = gc.get(f"/file/{input_id}")
        idoc = gc.get(f"/item/{fdoc['itemId']}")
        return fdoc, idoc
    except Exception:
        pass

    # Try as item id
    idoc = gc.get(f"/item/{input_id}")  # will raise if not an item
    files = list(gc.listFile(idoc["_id"]))  # generator -> list
    if not files:
        raise RuntimeError(f"Item {input_id} has no files.")

    # Prefer WSI extensions, else largest file
    def score(fd):
        name = fd.get("name", "").lower()
        ext = os.path.splitext(name)[1]
        is_wsi = ext in WSI_EXTS
        size = int(fd.get("size", 0))
        # sort key: prefer WSI (True > False), then by size
        return (1 if is_wsi else 0, size)

    fdoc = sorted(files, key=score, reverse=True)[0]
    return fdoc, idoc


# def _if_latest_subcompartments_annot(gc, item_id: str):
#     annots = list(gc.get(f"/annotation/item/{item_id}", parameters={"sort": "updated"}))
#     # newest last → search from end
#     for a in reversed(annots):
#         name = a.get("annotation", {}).get("name", "").strip()
#         if name == "glomerulus_subcompartments":
#             return True
#     return False


def _get_latest_glom_annot(gc, item_id: str):
    annots = list(gc.get(f"/annotation/item/{item_id}", parameters={"sort": "updated"}))
    # newest last → search from end
    for a in reversed(annots):
        name = a.get("annotation", {}).get("name", "").strip()
        if name == "non_globally_sclerotic_glomeruli":
            return a
    return None


def _get_all_subcompartment_annots(gc, item_id: str):
    """
    Retrieves all glomerulus_subcompartments annotations for an item.
    Returns a list of annotation documents.
    """
    annots = list(gc.get(f"/annotation/item/{item_id}", parameters={"sort": "updated"}))
    subcomp_annots = []
    for a in annots:
        name = a.get("annotation", {}).get("name", "").strip()
        # Be careful if the annotation name changes.
        if name == "glomerulus_subcompartments":
            subcomp_annots.append(a)
    return subcomp_annots


def _compute_average_params_from_annotations(annots):
    """
    Computes the average of nuc_thresh, eosin_thresh, nuc_min_size, and eos_min_size
    from a list of glomerulus_subcompartments annotations.
    Returns a dict with averaged int values, or None if no valid data.
    """
    if not annots:
        return None

    nuc_thresh_vals = []
    eosin_thresh_vals = []
    nuc_min_size_vals = []
    eos_min_size_vals = []

    for a in annots:
        attrs = a.get("annotation", {}).get("attributes", {})
        if not attrs:
            continue

        # Extract values from metadata
        if "nuc_thresh" in attrs:
            nuc_thresh_vals.append(int(attrs["nuc_thresh"]))
        if "eosin_thresh" in attrs:
            eosin_thresh_vals.append(int(attrs["eosin_thresh"]))
        if "nuc_min_size" in attrs:
            nuc_min_size_vals.append(int(attrs["nuc_min_size"]))
        if "eos_min_size" in attrs:
            eos_min_size_vals.append(int(attrs["eos_min_size"]))

    # If we collected any values, compute averages
    if not (
        nuc_thresh_vals or eosin_thresh_vals or nuc_min_size_vals or eos_min_size_vals
    ):
        return None

    result = {}
    if nuc_thresh_vals:
        result["nuc_thresh"] = int(sum(nuc_thresh_vals) / len(nuc_thresh_vals))
    if eosin_thresh_vals:
        result["eosin_thresh"] = int(sum(eosin_thresh_vals) / len(eosin_thresh_vals))
    if nuc_min_size_vals:
        result["nuc_min_size"] = int(sum(nuc_min_size_vals) / len(nuc_min_size_vals))
    if eos_min_size_vals:
        result["eos_min_size"] = int(sum(eos_min_size_vals) / len(eos_min_size_vals))

    return result


def main(args):
    set_logger()
    apiURL = str(args.girderApiUrl)
    token = str(args.girderToken)

    svs_file = str(args.svsFile)
    output_basename = f"glomerulus_subcompartments_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Get CLI parameter values
    nuc_thresh = int(args.nucThresh) or 215
    eosin_thresh = int(args.eosinThresh) or 50
    nuc_min_size = int(args.nucMinSize) or 80
    eos_min_size = int(args.eosMinSize) or 150

    logging.info(f"Using girderApiUrl: {apiURL}")
    logging.info(f"Using girderToken: {token[:4]}...{token[-4:]}")
    logging.info(f"Input SVS File: {svs_file}")

    logging.info(f"Output Basename: {output_basename}")

    # Initial CLI values (may be overridden later)
    logging.info(f"CLI Nuclei Threshold: {nuc_thresh}")
    logging.info(f"CLI Eosin Threshold: {eosin_thresh}")
    logging.info(f"CLI Nuclei Minimum Size: {nuc_min_size}")
    logging.info(f"CLI Eosin Minimum Size: {eos_min_size}")

    extraction_dir_id = None
    debug_masks_dir_id = None
    intermediate_upload_count = 0
    debug_upload_count = 0

    if args.extractionDir:
        extraction_dir_id = str(args.extractionDir).split("/")[-2]
        logging.info(f"Extraction Directory ID: {extraction_dir_id}")

    no_mask_crops = args.noMaskCrops or False
    logging.info(f"No Mask Crops: {no_mask_crops}")

    if args.debugMasksDir:
        debug_masks_dir_id = str(args.debugMasksDir).split("/")[-2]
        logging.info(f"Debug Masks Directory ID: {debug_masks_dir_id}")

    gc = girder_client.GirderClient(apiUrl=apiURL)
    gc.setToken(token)
    logging.info("Connected to Girder.")

    # 1) Resolve file & item (accept file _id OR item _id)
    fdoc, idoc = _resolve_file_and_item(gc, svs_file)
    file_id = fdoc["_id"]
    item_id = idoc["_id"]
    file_name = fdoc["name"]
    logging.info(f"Using item: {item_id} ({idoc.get('name', '')})")
    logging.info(f"Using file: {file_id} ({file_name})")

    # Check if we should process all glomeruli and use averaged parameters
    selected_ids = None
    use_averaged_params = False

    if args.glom_ids:
        glom_ids_str = str(args.glom_ids).strip()
        if glom_ids_str.lower() in ["all", ""]:
            # User wants to process all glomeruli
            use_averaged_params = True
            logging.info(
                "Processing ALL glomeruli - will check for existing parameters"
            )
        else:
            # User specified specific IDs
            selected_ids = [s.strip() for s in glom_ids_str.split(",") if s.strip()]
            logging.info(f"Processing selected glomeruli: {selected_ids}")
    else:
        # Empty field - process all and use averaged params
        use_averaged_params = True
        logging.info(
            "No glomeruli IDs specified - will process ALL and check for existing parameters"
        )

    # If processing all glomeruli, try to get averaged parameters from existing annotations
    if use_averaged_params:
        logging.info("Checking for existing glomerulus_subcompartments annotations...")
        subcomp_annots = _get_all_subcompartment_annots(gc, item_id)

        if subcomp_annots:
            logging.info(
                f"Found {len(subcomp_annots)} existing glomerulus_subcompartments annotations"
            )
            avg_params = _compute_average_params_from_annotations(subcomp_annots)

            if avg_params:
                # Use averaged parameters
                if "nuc_thresh" in avg_params:
                    nuc_thresh = avg_params["nuc_thresh"]
                    logging.info(f"Using AVERAGED Nuclei Threshold: {nuc_thresh}")
                if "eosin_thresh" in avg_params:
                    eosin_thresh = avg_params["eosin_thresh"]
                    logging.info(f"Using AVERAGED Eosin Threshold: {eosin_thresh}")
                if "nuc_min_size" in avg_params:
                    nuc_min_size = avg_params["nuc_min_size"]
                    logging.info(f"Using AVERAGED Nuclei Minimum Size: {nuc_min_size}")
                if "eos_min_size" in avg_params:
                    eos_min_size = avg_params["eos_min_size"]
                    logging.info(f"Using AVERAGED Eosin Minimum Size: {eos_min_size}")
            else:
                logging.info(
                    "No valid parameters found in existing annotations - using CLI values"
                )
        else:
            logging.info(
                "No existing glomerulus_subcompartments annotations found - using CLI values"
            )
    else:
        logging.info("Processing selected glomeruli - using CLI parameter values")

    # Final parameter values being used
    logging.info(f"FINAL Nuclei Threshold: {nuc_thresh}")
    logging.info(f"FINAL Eosin Threshold: {eosin_thresh}")
    logging.info(f"FINAL Nuclei Minimum Size: {nuc_min_size}")
    logging.info(f"FINAL Eosin Minimum Size: {eos_min_size}")

    # 2) Workdir + download SVS
    mounted_root = _pick_workdir()
    mounted_path = mounted_root
    svs_path = os.path.join(mounted_path, file_name)
    gc.downloadFile(file_id, svs_path)
    logging.info(f"Downloaded SVS to: {svs_path}")

    # 3) Get latest non_globally_sclerotic_glomeruli annotation
    glom = _get_latest_glom_annot(gc, item_id)
    if glom is None:
        raise RuntimeError(
            "No 'non_globally_sclerotic_glomeruli' annotation found on this item."
        )

    logging.info(f"Using annotation: {glom.get('_id')} (updated {glom.get('updated')})")

    # 4) Write that annotation into a temp JSON (if your pipeline expects a path)
    json_dir = os.path.join(mounted_path, "inputs")
    Path(json_dir).mkdir(parents=True, exist_ok=True)

    ngsg_json = os.path.join(json_dir, "non_globally_sclerotic_glomeruli.json")
    with open(ngsg_json, "w") as f:
        json.dump([glom["annotation"]], f)
    logging.info(f"Wrote annotation JSON to: {ngsg_json}")

    # 5) Output paths
    out_dir = os.path.join(mounted_path, "outputs")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    extraction_dir = os.path.join(mounted_path, "extractions")
    Path(extraction_dir).mkdir(parents=True, exist_ok=True)

    debug_masks_dir = os.path.join(mounted_path, "debug_masks")
    Path(debug_masks_dir).mkdir(parents=True, exist_ok=True)

    output_json_path = os.path.join(out_dir, output_basename)

    # 6) Run your pipeline (pick one of your implementations)
    logging.info("Running pipeline...")
    # (A) If using your stain-heuristic single-file pipeline:
    from SC_seg.Code.SC_seg_glom import integrated_pipeline_single

    integrated_pipeline_single(
        svs_file=svs_path,
        json_path=ngsg_json,  # path on disk
        extraction_dir=extraction_dir,
        output_json_path=output_json_path,
        nuc_thresh=nuc_thresh,
        eosin_thresh=eosin_thresh,
        debug_masks_dir=debug_masks_dir,
        no_mask_crops=no_mask_crops,
        nuc_min_size=nuc_min_size,
        eos_min_size=eos_min_size,
        selected_element_ids=selected_ids,  # =========added args=========
    )
    logging.info(f"Pipeline complete. Output JSON: {output_json_path}")

    # 7) Upload JSON back to the item
    if extraction_dir_id:
        for file in os.listdir(extraction_dir):
            full_path = os.path.join(extraction_dir, file)
            if os.path.isfile(full_path):
                gc.uploadFileToFolder(extraction_dir_id, full_path, filename=file)
                intermediate_upload_count += 1
        logging.info(
            f"Uploaded {intermediate_upload_count} intermediate extraction files to folder {extraction_dir_id}."
        )

    if debug_masks_dir_id:
        for file in os.listdir(debug_masks_dir):
            full_path = os.path.join(debug_masks_dir, file)
            if os.path.isfile(full_path):
                gc.uploadFileToFolder(debug_masks_dir_id, full_path, filename=file)
                debug_upload_count += 1
        logging.info(
            f"Uploaded {debug_upload_count} debug mask files to folder {debug_masks_dir_id}."
        )

    with open(output_json_path, "r") as f:
        payload = json.load(f)
        _ = gc.post(
            path="annotation",
            parameters={"itemId": item_id},
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        logging.info(f"Posting results to Girder item {item_id}...")

    uploaded = gc.uploadFileToItem(
        item_id, output_json_path, filename=output_basename, mimeType="application/json"
    )

    logging.info(
        json.dumps(
            {
                "status": "ok",
                "svs": svs_path,
                "output_json": output_json_path,
                "girder_item_id": item_id,
                "girder_uploaded_file_id": uploaded.get("_id"),
                "girder_uploaded_file_name": uploaded.get("name"),
                "extraction_dir_uploads": intermediate_upload_count,
                "debug_masks_dir_uploads": (
                    debug_upload_count if not no_mask_crops else 0
                ),
            }
        )
    )

    logging.info("Upload complete.")


if __name__ == "__main__":
    main(CLIArgumentParser().parse_args())