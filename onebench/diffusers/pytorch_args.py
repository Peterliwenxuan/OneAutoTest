import argparse
import os
import subprocess
import re
from timeit import default_timer as timer
import torch
from diffusers import (
    StableDiffusionPipeline,
    DPMSolverMultistepScheduler,
    DDPMScheduler,
    EulerDiscreteScheduler,
)

def gpu_memory_used():
    output = subprocess.check_output(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,used_gpu_memory",
            "--format=csv,noheader",
        ]
    )
    output = output.decode("utf-8").strip()
    my_pid = os.getpid()
    mem_used_by_me = 0
    for line in output.split("\n"):
        pid, mem_used = map(int, re.split(",? ", line)[:2])
        if pid == my_pid:
            mem_used_by_me += mem_used
    return mem_used_by_me

def parse_args():
    parser = argparse.ArgumentParser(description="Simple demo of image generation.")
    parser.add_argument(
        "--prompt",
        type=str,
        default="a dog, baroque painting, beautiful detailed intricate insanely detailed octane render trending on artstation, 8 k artistic photography, photorealistic, soft natural volumetric cinematic perfect light, chiaroscuro, award - winning photograph",
    )
    parser.add_argument("--model_id", type=str, default="CompVis/stable-diffusion-v1-4")
    parser.add_argument(
        "--num_images_per_prompt",
        type=int,
        default=10,
        help="The number of images to generate per prompt.",
    )
    parser.add_argument(
        "--num_inference_steps",
        type=int,
        default=50,
        help="The number of denoising steps. More denoising steps usually lead to a higher quality image at the expense of slower inference",
    )
    parser.add_argument(
        "--img_height",
        type=int,
        default=512,
        help="The height in pixels of the generated image.",
    )
    parser.add_argument(
        "--img_width",
        type=int,
        default=512,
        help="The width in pixels of the generated image.",
    )

    parser.add_argument(
        "--scheduler",
        type=str,
        default="ddpm",
        choices=["ddpm", "dmp"],
        help="Scheduler.",
    )
    parser.add_argument("--saving_path", type=str, default="pytorch-sd-output", help="Directory where the generated images will be saved")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    if args.scheduler == "dmp":
        model_scheduler = DPMSolverMultistepScheduler.from_pretrained(
            args.model_id, subfolder="scheduler"
        )
    else:
        model_scheduler = DDPMScheduler.from_pretrained(
            args.model_id, subfolder="scheduler"
        )

    if "stabilityai/stable-diffusion-2" == args.model_id:
        model_scheduler = EulerDiscreteScheduler.from_pretrained(
            args.model_id, subfolder="scheduler"
        )
    load_start = timer()
    pipe = StableDiffusionPipeline.from_pretrained(
        args.model_id,
        use_auth_token=True,
        revision="fp16",
        torch_dtype=torch.float16,
        scheduler=model_scheduler,
    )

    pipe = pipe.to("cuda")
    print(
                "[pytorch]",
                "[compile(s)]",
                f"{timer() - load_start}",
            )
    os.makedirs(args.saving_path, exist_ok=True)
    cmd = "nvidia-smi --query-gpu=timestamp,name,driver_version,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv"

    with torch.autocast("cuda"):
        for j in range(args.num_images_per_prompt):
            print("[pytorch]", "[gpu_memory]", f"{gpu_memory_used()} MiB")
            start = timer()
            images = pipe(
                args.prompt,
                width=args.img_width,
                height=args.img_height,
                num_inference_steps=args.num_inference_steps,
                compile_unet=True,
            ).images
            print(
                "[pytorch]",
                f"[{args.img_width}x{args.img_height}]",
                "[elapsed(s)]",
                "[pipe]",
                f"{timer() - start}",
            )
            save_start = timer()
            for i, image in enumerate(images):
                prompt = args.prompt.strip().replace("\n", " ")
                dst = os.path.join(args.saving_path, f"{prompt[:100]}-{j}-{i}.png")
                image.save(dst)
            print("[pytorch]", "[elapsed(s)]", "[save]", f"{timer() - save_start}")
            print("[pytorch]", "[last_gpu_memory]", f"{gpu_memory_used()} MiB")
