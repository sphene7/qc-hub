import { createApp } from "vue";
import App from "./App.vue";
import router from "./router.js";
import "./style.css";
import "./sampling.css";

createApp(App).use(router).mount("#app");
