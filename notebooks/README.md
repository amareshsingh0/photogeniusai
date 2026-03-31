# PhotoGenius AI – Colab Notebooks

## Photogenius_Colab_Test.ipynb

**Run on Google Colab** (no local NVIDIA GPU required). Colab provides a free T4 GPU.

1. Open [Google Colab](https://colab.research.google.com).
2. **File → Upload notebook** and select `Photogenius_Colab_Test.ipynb`,  
   or clone this repo and open the notebook from the `notebooks/` folder.
3. **Runtime → Change runtime type → T4 GPU**.
4. **Runtime → Run all**.

The notebook will:

- Install diffusers, torch, transformers, accelerate, peft, etc.
- Mount Google Drive (optional; outputs go to Drive when mounted).
- Check for GPU (no `nvidia-smi`; uses `torch.cuda`).
- Load SDXL on T4 and generate a test image.
- Prepare 8 sample images (dog-example dataset) and run LoRA training.
- Save generated image, LoRA weights, and training images to  
  `My Drive/photogenius_colab_output/`.

Includes error handling and progress bars (tqdm).
