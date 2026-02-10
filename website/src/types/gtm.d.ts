/**
 * GTM DataLayer type declarations.
 * Extends the Window interface to include the GTM dataLayer array.
 */

interface DataLayerEvent {
  event: string;
  [key: string]: unknown;
}

interface Window {
  dataLayer: DataLayerEvent[];
}
