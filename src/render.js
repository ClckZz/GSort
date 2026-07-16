const categorize_btn = document.getElementById("categorize-btn");
const how_many_input = document.getElementById("how_many_input");

categorize_btn.addEventListener("click", categorizePosts);
async function categorizePosts() {
  animate(how_many_input, {
    scale: [1.3, 1],
    duration: 400,
    ease: "outBack",
  });

  const response = await fetch(
    `http://127.0.0.1:8000/categorize?how_many=${parseInt(how_many_input.value)}`,
  );

  const data = await response.json();
  console.log(data);
}
