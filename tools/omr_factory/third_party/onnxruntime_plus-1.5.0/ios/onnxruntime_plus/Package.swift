// swift-tools-version: 5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "onnxruntime_plus",
    platforms: [
        .iOS("11.0")
    ],
    products: [
        .library(name: "onnxruntime-plus", targets: ["onnxruntime_plus"])
    ],
    dependencies: [
        .package(name: "FlutterFramework", path: "../FlutterFramework")
    ],
    targets: [
        .binaryTarget(
            name: "onnxruntimeC",
            url: "https://onnxruntimepackages.z14.web.core.windows.net/pod-archive-onnxruntime-c-1.15.1.zip",
            checksum: "f3c88ff2a8a49101efb65f6c578dc8fa99ca6e5298ed876e42b9f171a6d99724"
        ),
        .target(
            name: "onnxruntime_plus",
            dependencies: [
                .product(name: "FlutterFramework", package: "FlutterFramework"),
                "onnxruntimeC"
            ],
            linkerSettings: [
                .linkedLibrary("c++"),
                .unsafeFlags(["-weak_framework", "CoreML"])
            ]
        )
    ]
)