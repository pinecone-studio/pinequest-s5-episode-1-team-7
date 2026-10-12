"""Regenerate tests/fixtures/tiny_model.onnx (needs the `onnx` package from requirements-train.txt).

A stand-in for the real classifier with the same ONNX contract, so runtime tests need neither
torch nor the trained model: input "patches" float32 (N, 3, 32, 32), output "p_malignant" (N,).
It scores colourfulness, sigmoid(10 * (mean(max_c - min_c) - 0.2)): stained tissue ~0.75,
white background ~0.12. The 32 px input also exercises patch resizing.

    python tests/fixtures/make_tiny_model.py
"""
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

SIZE = 32


def build() -> onnx.ModelProto:
    nodes = [
        helper.make_node("ReduceMax", ["patches"], ["cmax"], axes=[1], keepdims=0),
        helper.make_node("ReduceMin", ["patches"], ["cmin"], axes=[1], keepdims=0),
        helper.make_node("Sub", ["cmax", "cmin"], ["chroma"]),
        helper.make_node("ReduceMean", ["chroma"], ["mean"], axes=[1, 2], keepdims=0),
        helper.make_node("Sub", ["mean", "offset"], ["centered"]),
        helper.make_node("Mul", ["centered", "gain"], ["logit"]),
        helper.make_node("Sigmoid", ["logit"], ["p_malignant"]),
    ]
    graph = helper.make_graph(
        nodes,
        "tiny_colourfulness",
        [helper.make_tensor_value_info("patches", TensorProto.FLOAT, ["batch", 3, SIZE, SIZE])],
        [helper.make_tensor_value_info("p_malignant", TensorProto.FLOAT, ["batch"])],
        initializer=[
            numpy_helper.from_array(np.array(0.2, dtype=np.float32), "offset"),
            numpy_helper.from_array(np.array(10.0, dtype=np.float32), "gain"),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)], producer_name="make_tiny_model")
    model.ir_version = 8
    onnx.checker.check_model(model)
    return model


if __name__ == "__main__":
    out = Path(__file__).with_name("tiny_model.onnx")
    onnx.save(build(), str(out))
    print(f"wrote {out}")
