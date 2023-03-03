#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>

int main() {
  const char* backupScriptPath = getenv("BACKUP_SCRIPT_PATH");
  if (!backupScriptPath) {
    printf("%s\n", "Missing backup script path");
    return 1;
  }

  execl("/usr/bin/python3", "/usr/bin/python3", backupScriptPath, NULL);
  printf("%s\n", "Exec failed");
  return 2;
}