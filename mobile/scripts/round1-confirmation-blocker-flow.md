# Round 1 -> Confirmation Blocker Flow

Track every Round 1 blocker through fix and confirmation rerun.

| blockerId | layer | severity | rootCause | fixCommit | requiredRerunScope | confirmedClosed |
| --- | --- | --- | --- | --- | --- | --- |
| env-adb-device-missing-20260418 | environment | P0 | Android device not visible in `adb devices -l` |  | `verify:rc-android` + `adb install -r` + Round 1 step 1 | no |
| env-jdk-missing-20260418 | environment | P0 | No local Java runtime for Gradle | local-only (no code commit) | `java -version` + `./gradlew -version` + `assembleRelease` | yes |
| task-insight-sample-* | tasks | P1 | Understanding card repeats task text, misclassifies weak context, or gives unsupported judgment |  | sample rerun + `npm run test:core` + relevant task detail checks | no |
