export async function uploadFile(file: File) {
  const formData = new FormData()
  formData.append("file", file)

  const res = await fetch("http://localhost:8000/files/upload", {
    method: "POST",
    body: formData,
  })

  return res.json()
}

export async function listFiles() {
  const res = await fetch("http://localhost:8000/files")
  return res.json()
}
