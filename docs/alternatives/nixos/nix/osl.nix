{ lib, python3Packages }:

python3Packages.buildPythonApplication {
  pname = "osl";
  version = "0.0.1";
  pyproject = true;
  build-system = [ python3Packages.setuptools ];
  src = lib.cleanSource ../.;
  doCheck = false; # tests run as the `unit` flake check
  meta.description = "Unified launcher core: detect format, pick runtime, apply recipes";
}
