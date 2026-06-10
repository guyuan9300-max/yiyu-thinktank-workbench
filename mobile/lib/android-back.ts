import { useFocusEffect, useRouter } from "expo-router";
import { useCallback } from "react";
import { BackHandler, Platform } from "react-native";

export function useAndroidBackHandler(handler: () => boolean) {
  useFocusEffect(
    useCallback(() => {
      if (Platform.OS !== "android") {
        return undefined;
      }

      const subscription = BackHandler.addEventListener("hardwareBackPress", () => handler());
      return () => subscription.remove();
    }, [handler]),
  );
}

export function useAndroidBackToTasks(handleLocalBack?: () => boolean) {
  const router = useRouter();

  useAndroidBackHandler(
    useCallback(() => {
      if (handleLocalBack?.()) {
        return true;
      }
      router.replace("/(tabs)/tasks");
      return true;
    }, [handleLocalBack, router]),
  );
}

export function useAndroidExitApp(handleLocalBack?: () => boolean) {
  useAndroidBackHandler(
    useCallback(() => {
      if (handleLocalBack?.()) {
        return true;
      }
      BackHandler.exitApp();
      return true;
    }, [handleLocalBack]),
  );
}
