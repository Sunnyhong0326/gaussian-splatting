import os

data_path = "../data"
data_file = ["iStaging_showroom_full"]

for data in data_file:
    data_pth = os.path.join(data_path, data)
    output_pth = os.path.join("./output", "iStaging_showroom_clean")
    os.makedirs(output_pth, exist_ok=True)
    report_pth = os.path.join("./output", data, "output.txt")
    with open(report_pth, "w") as fp:
        pass
    train_cmd = f"python train.py -s {data_pth} -m {output_pth} -i images_8 | tee {report_pth}"
    os.system(train_cmd)