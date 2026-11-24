document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".app-alert").forEach((alert) => {
    window.setTimeout(() => {
      if (window.bootstrap && alert.isConnected) {
        window.bootstrap.Alert.getOrCreateInstance(alert).close();
      }
    }, 6500);
  });
});
