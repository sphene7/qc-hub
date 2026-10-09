<template>
  <div class="login-container">
    <div class="login-box">
      <h1>{{ systemInfo?.system_name || 'Excel-to-Web 系统' }}</h1>
      <p class="subtitle">请登录以继续</p>
      
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="username">用户名</label>
          <input 
            type="text" 
            id="username"
            v-model="username" 
            required 
            placeholder="请输入用户名"
            autocomplete="username"
          />
        </div>
        
        <div class="form-group">
          <label for="password">密码</label>
          <input 
            type="password"
            id="password" 
            v-model="password" 
            required 
            placeholder="请输入密码"
            autocomplete="current-password"
          />
        </div>
        
        <div v-if="error" class="error-message">
          {{ error }}
        </div>
        
        <button type="submit" :disabled="loading" class="btn-login">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
      
      <div v-if="showTestAccounts" class="test-accounts">
        <p><strong>测试账号：</strong></p>
        <ul>
          <li>管理员: admin / admin123</li>
          <li>用户1: user1 / user123</li>
          <li>用户2: user2 / user123</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  systemInfo: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['login-success'])

const showTestAccounts = computed(() => props.systemInfo?.mode !== 'product')

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    })
    
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.detail || '登录失败')
    }
    
    const data = await response.json()
    
    // Save token and user info
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify(data.user))
    
    // Emit success event
    emit('login-success', data.user)
  } catch (err) {
    error.value = err.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #9b7fd4 0%, #7c5cbf 50%, #6b4aa8 100%);
  padding: 20px;
}

.login-box {
  background: var(--card);
  padding: 40px;
  border-radius: 14px;
  box-shadow: var(--shadow-lg);
  width: 100%;
  max-width: 400px;
}

h1 {
  margin: 0 0 10px 0;
  color: var(--ink);
  font-size: 28px;
  text-align: center;
}

.subtitle {
  margin: 0 0 30px 0;
  color: var(--muted);
  text-align: center;
  font-size: 14px;
}

.login-form {
  margin-bottom: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  color: var(--ink);
  font-weight: 500;
  font-size: 14px;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.3s;
}

.form-group input:focus {
  outline: none;
  border-color: var(--primary);
}

.error-message {
  padding: 10px;
  background: #fee;
  border: 1px solid #fcc;
  border-radius: 5px;
  color: #c33;
  font-size: 14px;
  margin-bottom: 15px;
}

.btn-login {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-2) 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s;
}

.btn-login:hover:not(:disabled) {
  transform: translateY(-2px);
}

.btn-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.test-accounts {
  padding: 15px;
  background: var(--bg-accent);
  border-radius: 8px;
  font-size: 13px;
}

.test-accounts p {
  margin: 0 0 10px 0;
  color: var(--muted);
}

.test-accounts ul {
  margin: 0;
  padding-left: 20px;
  color: var(--muted);
}

.test-accounts li {
  margin-bottom: 5px;
}
</style>
