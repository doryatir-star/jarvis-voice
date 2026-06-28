// קטלוג המוצרים — כל הפריטים שבמלאי, לפי קטגוריות ומחירים.
// המחיר בשקלים (₪).

export const categories = [
  {
    id: 'accessories',
    title: 'אביזרים',
    emoji: '🧸',
    products: [
      { id: 'squishy-blue-heart', name: 'סקושי ניקוי לב כחול', price: 5, emoji: '💙' },
      { id: 'keychain-stitch', name: "מחזיק מפתחות סטיץ'", price: 4, emoji: '🔑' },
      { id: 'labubu-doll', name: 'בובת לבובו', price: 5, emoji: '🧸' },
      { id: 'keychain-stitch-scooter', name: "מחזיק מפתחות סטיץ' קורקינט", price: 4, emoji: '🛴' },
      { id: 'keychain-stitch-ship', name: "מחזיק מפתחות סטיץ' על ספינה", price: 4, emoji: '🚢' },
      { id: 'eyeshadow-brush', name: 'מברשת לצללית', price: 5, emoji: '🖌️' },
      { id: 'white-clip', name: 'קליפס לבן', price: 5, emoji: '📎' },
      { id: 'markers', name: 'מרקרים', price: 5, emoji: '🖍️' },
      { id: 'keychain-mirror', name: 'מחזיק מפתחות של מראה', price: 4, emoji: '🪞' },
      { id: 'cute-tape', name: 'סלוטייפ יפה', price: 4, emoji: '🎀' },
    ],
  },
  {
    id: 'water-balloons',
    title: 'בלוני מים',
    emoji: '🎈',
    note: 'כל סוג — 5 ₪',
    products: [
      { id: 'balloon-red', name: 'בלוני מים אדום', price: 5, emoji: '🔴' },
      { id: 'balloon-orange', name: 'בלוני מים כתום', price: 5, emoji: '🟠' },
      { id: 'balloon-yellow', name: 'בלוני מים צהוב', price: 5, emoji: '🟡' },
      { id: 'balloon-green', name: 'בלוני מים ירוק', price: 5, emoji: '🟢' },
      { id: 'balloon-blue', name: 'בלוני מים כחול', price: 5, emoji: '🔵' },
      { id: 'beads-pink', name: 'בלוני חרוזים ורוד', price: 5, emoji: '🌸' },
      { id: 'beads-orange', name: 'בלוני חרוזים כתום', price: 5, emoji: '🧡' },
    ],
  },
]

// כל המוצרים ברשימה שטוחה אחת — שימושי לחיפוש ולעגלה.
export const allProducts = categories.flatMap((c) => c.products)

// מערכת הקופונים — קופון הנחה בשווי 15 ₪ על הרכישה.
export const coupons = {
  SAVE15: { code: 'SAVE15', discount: 15, label: 'הנחה של 15 ₪' },
  // ניתן להוסיף כאן קופונים נוספים בעתיד.
}
