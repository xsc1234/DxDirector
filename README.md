#### This is the core code for paper "DxDirector: an agentic large language model driving the full-process clinical diagnosis"


```
pip install -r requirements.txt
Typical install time: 30 minutes
```

### Instruction-tuning for full-process clinical diagnosis:

#### 1. make training data
```
python Instruction-Tuning-data-construction/make_data_stage1.py
python Instruction-Tuning-data-construction/make_data_stage2.py
python Instruction-Tuning-data-construction/make_data_stage3_add-think.py
```

#### 2. Instruction-tuning
The training needs 4 Nvidia A100 80G GPUS.
```
sh Instruction-Tuning/inst-ft_code_with_marks_think_at_step.sh
```

### Step-level strategy optimization:

#### 1. make training data
```
python Step-level-strategy-optimization/data_construction/rewards_for_multiple_strategy.py
```

#### 2. Training
The training needs 4 Nvidia A100 80G GPUS.
```
sh Step-level-strategy-optimization/train/slso_train.sh
```


### Inference
Need one Nvidia A100 80G GPU.
```
sh Inference/DxDirector.sh
Expected run time: 2s for a sample.
```

### Citation
```
@article{xu2026dxdirector,
  title={DxDirector: an agentic large language model driving the full-process clinical diagnosis},
  author={Xu, Shicheng and Huang, Xin and Wei, Zihao and Pang, Liang and Shen, Huawei and Cheng, Xueqi},
  journal={Nature Communications},
  year={2026},
  publisher={Nature Publishing Group}
}
```





