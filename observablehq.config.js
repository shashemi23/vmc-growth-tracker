// Observable Framework config. See https://observablehq.com/framework/config
export default {
  title: "VMC Growth Tracker",
  root: "src",
  theme: ["air", "near-midnight"],
  pages: [
    {name: "What it means for you", path: "/outlook"},
    {name: "Development pipeline", path: "/development"},
    {name: "Housing market", path: "/housing"},
    {name: "About the data", path: "/about"}
  ],
  head: '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏙️</text></svg>">',
  footer: "Data: York Region Open Data, CMHC Housing Market Information Portal, TRREB Market Watch, Bank of Canada. Not affiliated with the City of Vaughan or TRREB. Educational only, not financial advice.",
  toc: true,
  search: true
};
