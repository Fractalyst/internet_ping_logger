import cairosvg
import os


def get_script_path() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    input_dir = os.path.join(get_script_path(), "tray_icons_svg")
    output_dir = os.path.join(get_script_path(), "tray_icons_png")

    os.makedirs(output_dir, exist_ok=True)

    icons = [
        "internet_good.svg",
        "internet_warning.svg",
        "internet_none.svg",
    ]

    for icon in icons:
        svg_path = os.path.join(input_dir, icon)
        png_path = os.path.join(output_dir, os.path.splitext(icon)[0] + ".png")

        if not os.path.exists(svg_path):
            print(f"Missing SVG: {svg_path}")
            continue

        cairosvg.svg2png(
            url=svg_path, write_to=png_path, output_width=16, output_height=16
        )

        print(f"Converted: {icon} → {os.path.basename(png_path)}")


if __name__ == "__main__":
    main()
