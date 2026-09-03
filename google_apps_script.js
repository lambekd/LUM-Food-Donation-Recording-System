// Google Apps Script Template for Scale Logger Desktop App
// -------------------------------------------------------------
// Instructions:
// 1. Open your Google Sheet.
// 2. Click "Extensions" > "Apps Script".
// 3. Paste this code into the editor (replacing any existing code).
// 4. Click "Deploy" > "New deployment".
// 5. Select type: "Web app".
// 6. Set Description: "Scale App Webhook".
// 7. Set "Execute as": "Me".
// 8. Set "Who has access": "Anyone" (allows desktop app to POST without complex OAuth).
// 9. Click "Deploy", authorize access, and copy the Web App URL (starts with https://script.google.com/macros/s/...).
// 10. Paste the Web App URL into the Scale App Google Sheets Settings!

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // Auto-create header row if sheet is completely empty
    if (sheet.getLastRow() === 0) {
      sheet.appendRow([
        "Timestamp",
        "Donor",
        "Food Product",
        "Weight",
        "Unit",
        "Operator",
        "Notes"
      ]);
      // Format header row (bold & light gray background)
      var headerRange = sheet.getRange(1, 1, 1, 7);
      headerRange.setFontWeight("bold");
      headerRange.setBackground("#EFEFEF");
    }
    
    var data = JSON.parse(e.postData.contents);
    
    // Support single record or batch array of records
    var records = Array.isArray(data) ? data : [data];
    
    records.forEach(function(rec) {
      sheet.appendRow([
        rec.timestamp || new Date().toISOString(),
        rec.donor_name || rec.donor || "",
        rec.product_name || rec.product || "",
        parseFloat(rec.weight) || 0.0,
        rec.unit || "lbs",
        rec.operator || "",
        rec.notes || ""
      ]);
    });
    
    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "Appended " + records.length + " record(s) successfully",
      new_last_row: sheet.getLastRow()
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    message: "Scale Logger Webhook is active and healthy."
  })).setMimeType(ContentService.MimeType.JSON);
}
