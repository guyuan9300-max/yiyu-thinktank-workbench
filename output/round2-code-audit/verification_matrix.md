# Verification Matrix

| Repo | Check | Status | Evidence |
| --- | --- | --- | --- |
| main | build:main | fail | > yiyu-thinktank-workbench@0.1.0 build:main |
| main | build:renderer | fail | ✗ Build failed in 792ms |
| main | backend minimal pytest | fail | ==================================== ERRORS ==================================== |
| main | cloud minimal pytest | fail | F........FF...F..F.F                                                     [100%] |
| mobile | inventory:direct-api-usage | pass | > yiyu-mobile@1.0.0 inventory:direct-api-usage |
| mobile | check:no-direct-task-api-writes | pass | > yiyu-mobile@1.0.0 check:no-direct-task-api-writes |
| mobile | test:core | pass | > yiyu-mobile@1.0.0 test:core |
