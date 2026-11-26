// The Worker's entry point. All the logic is in observe.js, so the tests run
// it without a Worker; this file only hands it the request.
import {handle} from "./observe.js";

export default {
  fetch(request, env) {
    return handle(request, env);
  },
};
