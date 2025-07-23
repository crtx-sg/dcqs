import os
import argparse
import pydicom
from PIL import Image
import io
import base64

# --- Provider-Specific Imports ---
# These are imported dynamically based on the user's choice.

# --- Configuration ---
PROCESSED_REPORTS_DIR = "processed_reports"

# --- Function Definitions ---

def convert_dicom_to_png(dicom_path):
    """Converts a DICOM file to a PNG image."""
    try:
        dicom_file = pydicom.dcmread(dicom_path)
        image_data = dicom_file.pixel_array
        
        # Normalize pixel values for image conversion
        image_data = image_data - image_data.min()
        image_data = image_data / image_data.max()
        image_data = (image_data * 255).astype('uint8')
        
        image = Image.fromarray(image_data)
        
        # Convert image to a byte stream
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()

    except Exception as e:
        print(f"Error converting {dicom_path}: {e}")
        return None

def generate_report_with_ollama(image_bytes, model_name):
    """Generates a medical report from an image using an Ollama model."""
    try:
        import ollama
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        response = ollama.chat(
            model=model_name,
            messages=[
                {
                    'role': 'user',
                    'content': 'Generate a detailed medical report for this image.',
                    'images': [image_base64]
                }
            ]
        )
        return response['message']['content']
    except Exception as e:
        print(f"Error with Ollama: {e}")
        return None

def generate_report_with_huggingface(image_bytes, model_name):
    """Generates a medical report from an image using a Hugging Face model."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            device_map="auto"
        )
        
        image = Image.open(io.BytesIO(image_bytes))
        prompt = tokenizer.from_list_of_messages([
            {"role": "user", "content": [image, "Generate a detailed medical report for this image."]}
        ])
        
        inputs = prompt.to(model.device)
        generation = model.generate(**inputs, max_new_tokens=1024)
        report = tokenizer.decode(generation[0], skip_special_tokens=True)
        return report
    except Exception as e:
        print(f"Error with Hugging Face: {e}")
        return None

def generate_report_with_cohere(image_bytes, model_name):
    """Generates a medical report from an image using a Cohere model."""
    try:
        import cohere
        co = cohere.Client(os.environ.get("COHERE_API_KEY"))
        
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        response = co.chat(
            model=model_name,
            messages=[
                {
                    "role": "User",
                    "content": [
                        {"type": "text", "text": "Generate a detailed medical report for this image."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}}
                    ]
                }
            ]
        )
        return response.text
    except Exception as e:
        print(f"Error with Cohere: {e}")
        return None

# --- Main Execution ---

def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Process DICOM files and generate medical reports.")
    parser.add_argument("dicom_dir", help="Directory containing DICOM files to process.")
    parser.add_argument("--provider", choices=["ollama", "huggingface", "cohere"], default="ollama", help="The AI provider to use.")
    parser.add_argument("--model", help="The name of the model to use.")
    args = parser.parse_args()

    # --- Model Name Validation ---
    if not args.model:
        if args.provider == "huggingface":
            args.model = "google/medgemma-1.0-7b-it"
        elif args.provider == "cohere":
            args.model = "command-r-plus" 
        else: # ollama
            args.model = "medgemma"
            
    # --- Directory Setup ---
    if not os.path.exists(PROCESSED_REPORTS_DIR):
        os.makedirs(PROCESSED_REPORTS_DIR)

    # --- File Processing ---
    for filename in os.listdir(args.dicom_dir):
        dicom_path = os.path.join(args.dicom_dir, filename)
        
        if not os.path.isfile(dicom_path):
            continue

        print(f"Processing {filename} with {args.provider}...")
        
        image_bytes = convert_dicom_to_png(dicom_path)
        if not image_bytes:
            continue
            
        report = None
        if args.provider == "ollama":
            report = generate_report_with_ollama(image_bytes, args.model)
        elif args.provider == "huggingface":
            report = generate_report_with_huggingface(image_bytes, args.model)
        elif args.provider == "cohere":
            report = generate_report_with_cohere(image_bytes, args.model)
            
        if not report:
            print(f"Failed to generate report for {filename}")
            continue
            
        report_filename = f"{os.path.splitext(filename)[0]}.txt"
        report_path = os.path.join(PROCESSED_REPORTS_DIR, report_filename)
        
        with open(report_path, "w") as f:
            f.write(report)
            
        print(f"Report saved to {report_path}")

if __name__ == "__main__":
    main()
