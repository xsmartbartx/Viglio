// Single source of truth for user-visible naming (README.md "Branding") —
// nothing hardcodes the product name here either, same rule as the Python
// side. Node can't call `vigilo_core.config()`, so this is a plain static
// JSON import instead.
import brandConfig from "../../../brand.config.json";

export const brand = brandConfig.brand;
export const theme = brandConfig.theme;
export const namespaces = brandConfig.namespaces;
