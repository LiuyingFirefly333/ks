import { ref } from 'vue'

import { courseApi } from '../api/index.js'

export function useCourses() {
  const courses = ref([])
  const currentCourseId = ref('')
  const loadingCourses = ref(false)

  async function loadCourses(onInitialCourse) {
    loadingCourses.value = true
    try {
      courses.value = await courseApi.list()
      if (!currentCourseId.value && courses.value.length) {
        currentCourseId.value = courses.value[0].id
        await onInitialCourse?.(currentCourseId.value)
      }
    } catch {
      courses.value = []
    } finally {
      loadingCourses.value = false
    }
  }

  async function selectCourse(courseId, onChange) {
    if (!courseId || currentCourseId.value === courseId) return false
    currentCourseId.value = courseId
    await onChange?.(courseId)
    return true
  }

  return {
    courses,
    currentCourseId,
    loadingCourses,
    loadCourses,
    selectCourse,
  }
}
