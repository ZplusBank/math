#include <iostream>
#include <cstdlib>

int main() {
    std::cout << "Trying pip3 first..." << std::endl;

    // Try pip3 uninstall
    int result = system("pip3 uninstall -y ttkbootstrap");

    if (result != 0) {
        std::cout << "pip3 not found. Trying pip..." << std::endl;
        system("pip uninstall -y ttkbootstrap");
    }

    std::cout << "Installing ttkbootstrap >= 1.10.1..." << std::endl;

    // Try pip3 install
    result = system("pip3 install \"ttkbootstrap>=1.10.1\"");

    if (result != 0) {
        std::cout << "pip3 install failed. Trying pip..." << std::endl;
        system("pip install \"ttkbootstrap>=1.10.1\"");
    }

    std::cout << "Finished." << std::endl;

    return 0;
}
