#include <windows.h>
#include <dbghelp.h>
#include <iostream>
#include <fstream>
#include <vector>
#include <ctime>
#include <sstream>



#pragma comment(lib, "dbghelp.lib")

#define MAX_FRAMES 64

CRITICAL_SECTION cs;  // thread-safe logging


template <typename T>
std::string type_ToStr(T t){
    std::stringstream ss ;
    ss <<  t ;
    return ss.str();
}

// ---------------- SYSTEM INFO ----------------
void write_system_info(std::ofstream &file) {
    MEMORYSTATUSEX memInfo;
    memInfo.dwLength = sizeof(memInfo);
    GlobalMemoryStatusEx(&memInfo);

    file << "\"memory\": {";
    file << "\"total_phys\": " << memInfo.ullTotalPhys << ",";
    file << "\"avail_phys\": " << memInfo.ullAvailPhys;
    file << "}";
}

// ---------------- BACKTRACE ----------------
std::vector<std::string> get_backtrace() {
    void* stack[MAX_FRAMES];
    USHORT frames = CaptureStackBackTrace(0, MAX_FRAMES, stack, NULL);

    SYMBOL_INFO* symbol = (SYMBOL_INFO*)calloc(sizeof(SYMBOL_INFO) + 256, 1);
    symbol->MaxNameLen = 255;
    symbol->SizeOfStruct = sizeof(SYMBOL_INFO);

    HANDLE process = GetCurrentProcess();
    SymInitialize(process, NULL, TRUE);

    std::vector<std::string> result;

    for (USHORT i = 0; i < frames; i++) {
        SymFromAddr(process, (DWORD64)(stack[i]), 0, symbol);

        std::string frame = std::string(symbol->Name) + " - 0x" + type_ToStr(symbol->Address);
        result.push_back(frame);
    }
    //type_ToStr

    free(symbol);
    return result;
}

// ---------------- CRASH HANDLER ----------------
LONG WINAPI crash_handler(EXCEPTION_POINTERS* exceptionInfo) {
    EnterCriticalSection(&cs);

    std::ofstream file("crash_report.json");

    time_t now = time(0);

    file << "{";
    file << "\"timestamp\": " << now << ",";
    file << "\"exception_code\": " << exceptionInfo->ExceptionRecord->ExceptionCode << ",";

    // Backtrace
    auto bt = get_backtrace();
    int  i = 0;
    file << "\"backtrace\": [";
    for (; i < bt.size(); i++) {
        file << "\"" << bt[i] << "\"";
        if (i < bt.size() - 1) file << ",";
    }
    file << "],";

    // System info
    write_system_info(file);

    file << "}";

    file.close();

    LeaveCriticalSection(&cs);

    return EXCEPTION_EXECUTE_HANDLER;
}

// ---------------- MAIN ----------------
int main() {
    InitializeCriticalSection(&cs);

    SetUnhandledExceptionFilter(crash_handler);

    // Simulate crash
    int* p = NULL ;
    *p = 10;

    DeleteCriticalSection(&cs);
    return 0;
}