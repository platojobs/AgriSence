// AgriSense 病害识别页：上传图片 -> 调用模拟 AI 识别 -> 展示结果 + 历史记录
// 依赖：jQuery、dashboard.js（API_BASE）

let currentFile = null;
let history = [];

function handleFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) { alert("请选择图片文件"); return; }
  currentFile = file;
  const reader = new FileReader();
  reader.onload = function (e) {
    $("#preview-img").attr("src", e.target.result);
    $("#preview-wrap").removeClass("d-none");
    $("#btn-detect").prop("disabled", false);
  };
  reader.readAsDataURL(file);
}

function detect() {
  if (!currentFile) return;
  $("#result-box").addClass("d-none");
  $("#result-empty").addClass("d-none");
  $("#loading").removeClass("d-none");

  const fd = new FormData();
  fd.append("image", currentFile);

  $.ajax({
    url: API_BASE + "/api/disease/detect",
    method: "POST",
    data: fd,
    processData: false,
    contentType: false,
    success: function (res) {
      $("#loading").addClass("d-none");
      $("#result-box").removeClass("d-none");
      $("#r-disease").text(res.disease);
      $("#r-conf").text((res.confidence * 100).toFixed(1) + "%");
      $("#r-crop").text(res.crop);
      $("#r-symptom").text(res.symptom);
      $("#r-suggestion").text(res.suggestion);

      // 加入历史记录
      history.unshift({
        time: new Date().toLocaleString("zh-CN"),
        thumb: $("#preview-img").attr("src"),
        disease: res.disease,
        crop: res.crop,
        confidence: res.confidence,
      });
      renderHistory();
    },
    error: function () {
      $("#loading").addClass("d-none");
      $("#result-empty").removeClass("d-none");
      alert("识别失败，请重试");
    },
  });
}

function renderHistory() {
  const tbody = $("#history-table");
  if (history.length === 0) {
    tbody.html('<tr><td colspan="5" class="text-center text-muted py-3">暂无识别记录</td></tr>');
    return;
  }
  tbody.html(history.slice(0, 10).map((h) => `
    <tr>
      <td class="text-nowrap">${h.time}</td>
      <td><img src="${h.thumb}" alt="" style="width:40px;height:40px;object-fit:cover;border-radius:4px" /></td>
      <td>${h.disease}</td>
      <td>${h.crop}</td>
      <td>${(h.confidence * 100).toFixed(1)}%</td>
    </tr>
  `).join(""));
}

$(document).ready(function () {
  $("#upload-zone").on("click", () => $("#file-input").click());
  $("#file-input").on("change", function () { handleFile(this.files[0]); });

  // 拖拽
  $("#upload-zone").on("dragover", function (e) { e.preventDefault(); $(this).css("border-color", "#198754"); });
  $("#upload-zone").on("dragleave", function () { $(this).css("border-color", "#ced4da"); });
  $("#upload-zone").on("drop", function (e) {
    e.preventDefault();
    $(this).css("border-color", "#ced4da");
    handleFile(e.originalEvent.dataTransfer.files[0]);
  });

  $("#btn-detect").on("click", detect);
});
